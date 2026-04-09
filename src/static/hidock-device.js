/**
 * HiDock Device - WebUSB browser module
 *
 * Implements the full HiDock communication protocol using the browser WebUSB API.
 * Replaces the former Python pyusb backend device access.
 */

class HiDockDevicePacket {
    static SYNC = new Uint8Array([0x12, 0x34]);
    static HEADER_SIZE = 12;
    static MAX_BUF = 51200;

    constructor(cmd, seq, body) {
        this.cmd = cmd;
        this.seq = seq;
        this.body = body instanceof Uint8Array ? body : new Uint8Array(body || []);
    }

    encode() {
        const bodyLen = this.body.length;
        const buf = new ArrayBuffer(HiDockDevicePacket.HEADER_SIZE + bodyLen);
        const view = new DataView(buf);
        const arr = new Uint8Array(buf);
        // sync
        arr[0] = 0x12;
        arr[1] = 0x34;
        // cmd (big-endian u16)
        view.setUint16(2, this.cmd, false);
        // seq (big-endian u32)
        view.setUint32(4, this.seq, false);
        // body length (big-endian u32)
        view.setUint32(8, bodyLen, false);
        // body
        arr.set(this.body, HiDockDevicePacket.HEADER_SIZE);
        return arr;
    }

    static decode(raw) {
        if (raw.length < HiDockDevicePacket.HEADER_SIZE) {
            throw new Error(`Packet too short (${raw.length} bytes)`);
        }
        // Find sync bytes
        let idx = -1;
        for (let i = 0; i <= raw.length - 2; i++) {
            if (raw[i] === 0x12 && raw[i + 1] === 0x34) {
                idx = i;
                break;
            }
        }
        if (idx < 0) {
            throw new Error(`No sync bytes found in ${raw.length} bytes`);
        }
        const data = raw.slice(idx);
        if (data.length < HiDockDevicePacket.HEADER_SIZE) {
            throw new Error(`Packet too short after sync (${data.length} bytes)`);
        }
        const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
        const cmd = view.getUint16(2, false);
        const seq = view.getUint32(4, false);
        const bodyLen = view.getUint32(8, false);
        const body = data.slice(12, 12 + bodyLen);
        return new HiDockDevicePacket(cmd, seq, body);
    }
}

class HiDockDevice {
    static VENDOR_ID = 0x10D6;
    static PRODUCT_IDS = {
        0xB00C: "HiDock H1",
        0xB00D: "HiDock H1E",
        0xB00E: "HiDock P1",
    };
    static PRODUCT_ID_LIST = [0xB00C, 0xB00D, 0xB00E];

    static USB_INTERFACE = 0;
    static ENDPOINT_OUT = 1;  // endpoint number (address 0x01)
    static ENDPOINT_IN = 2;   // endpoint number (address 0x82)

    static CMD_GET_DEVICE_INFO = 0x01;
    static CMD_GET_DEVICE_TIME = 0x02;
    static CMD_GET_FILE_LIST = 0x04;
    static CMD_TRANSFER_FILE = 0x05;
    static CMD_GET_FILE_COUNT = 0x06;
    static CMD_DELETE_FILE = 0x07;
    static CMD_GET_CARD_INFO = 0x10;

    constructor(usbDevice) {
        this._dev = usbDevice;
        this._seq = 0;
        this._rxbuf = new Uint8Array(0);
        this.model = HiDockDevice.PRODUCT_IDS[usbDevice.productId] || `Unknown (0x${usbDevice.productId.toString(16).padStart(4, "0")})`;
        this.serial = "";
        this.version = "";
    }

    /** Check whether WebUSB is available in this browser. */
    static isSupported() {
        return !!(navigator && navigator.usb);
    }

    /** Prompt the user to select a HiDock device (required once for pairing). */
    static async requestDevice() {
        const filters = HiDockDevice.PRODUCT_ID_LIST.map(pid => ({
            vendorId: HiDockDevice.VENDOR_ID,
            productId: pid,
        }));
        const dev = await navigator.usb.requestDevice({ filters });
        return new HiDockDevice(dev);
    }

    /** Get already-paired HiDock devices (no user prompt). */
    static async getDevices() {
        const all = await navigator.usb.getDevices();
        return all
            .filter(d => d.vendorId === HiDockDevice.VENDOR_ID && HiDockDevice.PRODUCT_ID_LIST.includes(d.productId))
            .map(d => new HiDockDevice(d));
    }

    async open() {
        await this._dev.open();
        if (this._dev.configuration === null) {
            await this._dev.selectConfiguration(1);
        }
        await this._dev.claimInterface(HiDockDevice.USB_INTERFACE);
    }

    async close() {
        try {
            await this._dev.releaseInterface(HiDockDevice.USB_INTERFACE);
        } catch (_) { /* ignore */ }
        try {
            await this._dev.close();
        } catch (_) { /* ignore */ }
    }

    _nextSeq() {
        this._seq += 1;
        return this._seq;
    }

    async _send(pkt) {
        const data = pkt.encode();
        await this._dev.transferOut(HiDockDevice.ENDPOINT_OUT, data);
    }

    async _recv(timeoutMs = 3000) {
        const deadline = performance.now() + timeoutMs;

        while (performance.now() < deadline) {
            // Check rxbuf for a complete packet
            const syncIdx = this._findSync(this._rxbuf);
            if (syncIdx >= 0) {
                // Trim bytes before sync
                if (syncIdx > 0) {
                    this._rxbuf = this._rxbuf.slice(syncIdx);
                }
                if (this._rxbuf.length >= HiDockDevicePacket.HEADER_SIZE) {
                    const view = new DataView(this._rxbuf.buffer, this._rxbuf.byteOffset, this._rxbuf.byteLength);
                    const bodyLen = view.getUint32(8, false);
                    const total = HiDockDevicePacket.HEADER_SIZE + bodyLen;
                    if (this._rxbuf.length >= total) {
                        const pktBytes = this._rxbuf.slice(0, total);
                        this._rxbuf = this._rxbuf.slice(total);
                        return HiDockDevicePacket.decode(pktBytes);
                    }
                }
            }

            const remaining = Math.max(1, deadline - performance.now());
            const chunkTimeout = Math.min(remaining, 1000);

            try {
                const result = await Promise.race([
                    this._dev.transferIn(HiDockDevice.ENDPOINT_IN, HiDockDevicePacket.MAX_BUF),
                    new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), chunkTimeout)),
                ]);
                if (result.data && result.data.byteLength > 0) {
                    const chunk = new Uint8Array(result.data.buffer, result.data.byteOffset, result.data.byteLength);
                    this._appendRxBuf(chunk);
                }
            } catch (e) {
                if (e.message === "timeout") continue;
                throw e;
            }
        }
        return null;
    }

    _findSync(buf) {
        for (let i = 0; i <= buf.length - 2; i++) {
            if (buf[i] === 0x12 && buf[i + 1] === 0x34) return i;
        }
        return -1;
    }

    _appendRxBuf(chunk) {
        const merged = new Uint8Array(this._rxbuf.length + chunk.length);
        merged.set(this._rxbuf, 0);
        merged.set(chunk, this._rxbuf.length);
        this._rxbuf = merged;
    }

    async _command(cmd, body = new Uint8Array(0), timeoutMs = 5000) {
        const seq = this._nextSeq();
        await this._send(new HiDockDevicePacket(cmd, seq, body));
        return await this._recv(timeoutMs);
    }

    // ─── High-level commands ────────────────────────────────────

    async getDeviceInfo() {
        const resp = await this._command(HiDockDevice.CMD_GET_DEVICE_INFO);
        if (!resp || resp.body.length < 4) {
            return { model: this.model, version: "?", serial: "?" };
        }
        const view = new DataView(resp.body.buffer, resp.body.byteOffset, resp.body.byteLength);
        const verNum = view.getUint32(0, false);
        const major = (verNum >> 16) & 0xFF;
        const minor = (verNum >> 8) & 0xFF;
        const patch = verNum & 0xFF;
        this.version = `${major}.${minor}.${patch}`;

        if (resp.body.length >= 20) {
            this.serial = new TextDecoder("ascii").decode(resp.body.slice(4, 20)).replace(/\0+$/, "");
        } else {
            this.serial = new TextDecoder("ascii").decode(resp.body.slice(4)).replace(/\0+$/, "");
        }
        return { model: this.model, version: this.version, serial: this.serial };
    }

    async getDeviceTime() {
        const resp = await this._command(HiDockDevice.CMD_GET_DEVICE_TIME);
        if (!resp || resp.body.length < 7) return "?";
        return HiDockDevice._parseBcdDatetime(resp.body);
    }

    async getFileCount() {
        const resp = await this._command(HiDockDevice.CMD_GET_FILE_COUNT);
        if (!resp || resp.body.length < 4) return 0;
        const view = new DataView(resp.body.buffer, resp.body.byteOffset, resp.body.byteLength);
        return view.getUint32(0, false);
    }

    async listFiles() {
        const expected = await this.getFileCount();
        if (expected === 0) return [];

        const seq = this._nextSeq();
        await this._send(new HiDockDevicePacket(HiDockDevice.CMD_GET_FILE_LIST, seq, new Uint8Array(0)));

        const chunks = [];
        let consecutiveTimeouts = 0;
        const maxTimeouts = 5;

        while (consecutiveTimeouts < maxTimeouts) {
            const resp = await this._recv(2000);
            if (resp === null) {
                consecutiveTimeouts++;
                continue;
            }
            consecutiveTimeouts = 0;
            if (resp.cmd !== HiDockDevice.CMD_GET_FILE_LIST) continue;
            if (resp.body.length === 0) break;

            chunks.push(resp.body);
            const files = HiDockDevice._parseFileListChunks(chunks);
            if (expected > 0 && files.length >= expected) break;
        }

        return HiDockDevice._parseFileListChunks(chunks);
    }

    async downloadFile(filename, fileLength, onProgress = null) {
        const seq = this._nextSeq();
        const body = new TextEncoder().encode(filename);
        await this._send(new HiDockDevicePacket(HiDockDevice.CMD_TRANSFER_FILE, seq, body));

        const chunks = [];
        let received = 0;
        let consecutiveTimeouts = 0;
        const maxTimeouts = 10;

        while (received < fileLength && consecutiveTimeouts < maxTimeouts) {
            const resp = await this._recv(5000);
            if (resp === null) {
                consecutiveTimeouts++;
                continue;
            }
            consecutiveTimeouts = 0;
            if (resp.cmd !== HiDockDevice.CMD_TRANSFER_FILE) continue;
            if (resp.body.length === 0) break;

            // Check for "fail" response
            if (resp.body.length === 4) {
                const text = new TextDecoder("ascii").decode(resp.body);
                if (text === "fail") {
                    throw new Error(`Device reported download failure for '${filename}'`);
                }
            }

            chunks.push(resp.body);
            received += resp.body.length;

            if (onProgress) onProgress(received, fileLength);
        }

        // Concatenate chunks
        const result = new Uint8Array(received);
        let offset = 0;
        for (const chunk of chunks) {
            result.set(chunk, offset);
            offset += chunk.length;
        }
        return result;
    }

    async deleteFile(filename) {
        const body = new TextEncoder().encode(filename);
        const resp = await this._command(HiDockDevice.CMD_DELETE_FILE, body, 10000);
        if (!resp || resp.body.length < 1) return { result: "failed" };
        const code = resp.body[0];
        if (code === 0x00) return { result: "success" };
        if (code === 0x01) return { result: "not-exists" };
        return { result: "failed" };
    }

    async getCardInfo() {
        const resp = await this._command(HiDockDevice.CMD_GET_CARD_INFO, new Uint8Array(0), 5000);
        if (!resp || resp.body.length < 12) return null;
        const view = new DataView(resp.body.buffer, resp.body.byteOffset, resp.body.byteLength);
        const freeMib = view.getUint32(0, false);
        const capacityMib = view.getUint32(4, false);
        const status = view.getUint32(8, false);
        const mib = 1024 * 1024;
        const capacity = capacityMib * mib;
        const used = capacity - (freeMib * mib);
        return { used, capacity, status: status.toString(16).toUpperCase() };
    }

    // ─── Helpers / parsers ──────────────────────────────────────

    static _bcdToStr(b) {
        return `${(b >> 4) & 0xF}${b & 0xF}`;
    }

    static _parseBcdDatetime(data) {
        let s = "";
        for (let i = 0; i < 7 && i < data.length; i++) {
            s += HiDockDevice._bcdToStr(data[i]);
        }
        return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)} ${s.slice(8, 10)}:${s.slice(10, 12)}:${s.slice(12, 14)}`;
    }

    static _parseFileListChunks(chunks) {
        if (!chunks.length) return [];

        // Concatenate all chunks
        let totalLen = 0;
        for (const c of chunks) totalLen += c.length;
        const data = new Uint8Array(totalLen);
        let pos = 0;
        for (const c of chunks) {
            data.set(c, pos);
            pos += c.length;
        }

        let offset = 0;
        if (data.length >= 6 && data[0] === 0xFF && data[1] === 0xFF) {
            offset = 6;
        }

        const files = [];
        while (offset + 31 <= data.length) {
            try {
                const f = {};
                f.recording_type = data[offset];
                offset += 1;
                offset += 2; // skip 2 bytes
                const nameLen = data[offset];
                offset += 1;

                if (offset + nameLen + 26 > data.length) break;

                f.name = new TextDecoder("ascii").decode(data.slice(offset, offset + nameLen)).replace(/\0+$/, "");
                offset += nameLen;

                const view = new DataView(data.buffer, data.byteOffset + offset, 4);
                f.length = view.getUint32(0, false);
                offset += 4;
                offset += 6; // skip 6 bytes
                f.signature = Array.from(data.slice(offset, offset + 16)).map(b => b.toString(16).padStart(2, "0")).join("");
                offset += 16;

                const dt = HiDockDevice._parseFilenameDatetime(f.name);
                f.create_date = dt.date;
                f.create_time = dt.time;
                f.duration = HiDockDevice._calcDuration(f.length);

                files.push(f);
            } catch (e) {
                break;
            }
        }
        return files;
    }

    static _parseFilenameDatetime(name) {
        const months = {
            Jan: "01", Feb: "02", Mar: "03", Apr: "04", May: "05", Jun: "06",
            Jul: "07", Aug: "08", Sep: "09", Oct: "10", Nov: "11", Dec: "12",
        };
        const m = name.match(/^(\d{4})(\w{3})(\d{2})-(\d{2})(\d{2})(\d{2})-/);
        if (m) {
            const monNum = months[m[2]] || "??";
            return {
                date: `${m[1]}/${monNum}/${m[3]}`,
                time: `${m[4]}:${m[5]}:${m[6]}`,
            };
        }
        return { date: "", time: "" };
    }

    static _calcDuration(length) {
        return length / 8000;
    }

    /** Strip known audio extensions to get bare name. */
    static bareName(name) {
        return name.replace(/\.(hda|mp3|wav|m4a|ogg|webm|flac|aac|wma)$/i, "");
    }
}

// Export for use as module or global
if (typeof window !== "undefined") {
    window.HiDockDevice = HiDockDevice;
    window.HiDockDevicePacket = HiDockDevicePacket;
}

