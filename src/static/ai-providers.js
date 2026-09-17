/**
 * AgenDino AI Provider selection helpers.
 *
 * Exposes window.AIProviders, used by the Dashboard, Calendar, and Knowledge Base
 * to pick between the configured AI providers (Gemini / DeepSeek) for each action.
 *
 * The available providers are injected by the server as window.__AI_CONFIG__.
 */
(function () {
    'use strict';

    const raw = (window.__AI_CONFIG__ && typeof window.__AI_CONFIG__ === 'object')
        ? window.__AI_CONFIG__
        : {};

    const providers = (Array.isArray(raw.providers) && raw.providers.length > 0)
        ? raw.providers
        : [{ id: 'gemini', name: 'Gemini AI', model: '', configured: true }];

    const defaultProvider = raw.default_provider
        || (providers.find(p => p.configured) || providers[0]).id;

    function getProviders() {
        return providers.slice();
    }

    function getDefault() {
        return defaultProvider;
    }

    function getProvider(id) {
        return providers.find(p => p.id === id) || null;
    }

    function optionLabel(provider) {
        return provider.model ? provider.name + ' (' + provider.model + ')' : provider.name;
    }

    function fallbackProvider() {
        return providers.find(p => p.id === defaultProvider && p.configured)
            || providers.find(p => p.configured)
            || providers[0];
    }

    /** Populate a <select> with the configured providers, defaulting to the active one. */
    function populateSelect(select, opts) {
        if (!select) return;
        opts = opts || {};
        const configured = providers.filter(p => p.configured);
        const list = configured.length > 0 ? configured : providers;

        select.innerHTML = '';
        list.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = optionLabel(p);
            if (!p.configured) opt.disabled = true;
            select.appendChild(opt);
        });

        const preferred = opts.selected || defaultProvider;
        if (list.some(p => p.id === preferred)) {
            select.value = preferred;
        } else if (list.length > 0) {
            select.value = list[0].id;
        }
    }

    /** The provider currently selected by a split control (element or data-ai-split value). */
    function selected(name) {
        const el = typeof name === 'string'
            ? document.querySelector('[data-ai-split="' + name + '"]')
            : name;
        return (el && el.dataset.aiProvider) || defaultProvider;
    }

    function closeAllMenus(except) {
        document.querySelectorAll('[data-ai-menu]').forEach(menu => {
            if (menu === except) return;
            menu.classList.add('d-none');
            const toggle = menu.parentElement
                && menu.parentElement.querySelector('[data-ai-toggle]');
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
        });
    }

    function initSplit(container) {
        if (!container || container.dataset.aiReady) return;
        container.dataset.aiReady = '1';

        const menu = container.querySelector('[data-ai-menu]');
        const toggle = container.querySelector('[data-ai-toggle]');
        const main = container.querySelector('[data-ai-main]');
        if (!menu) return;

        if (!container.dataset.aiProvider) {
            container.dataset.aiProvider = fallbackProvider().id;
        }

        function render() {
            const current = container.dataset.aiProvider;
            menu.innerHTML = providers.map(p => {
                const active = p.id === current ? ' active' : '';
                const disabled = p.configured ? '' : ' disabled';
                const note = p.configured
                    ? ''
                    : '<small class="text-muted ms-auto">not configured</small>';
                return '<button type="button" class="ai-split-item' + active + '" data-provider="'
                    + p.id + '"' + disabled + '><i class="bi bi-check2"></i><span>'
                    + optionLabel(p) + '</span>' + note + '</button>';
            }).join('');
        }

        function close() {
            menu.classList.add('d-none');
            if (toggle) toggle.setAttribute('aria-expanded', 'false');
        }

        function open() {
            closeAllMenus(menu);
            menu.classList.remove('d-none');
            if (toggle) toggle.setAttribute('aria-expanded', 'true');
        }

        render();

        if (toggle) {
            toggle.addEventListener('click', e => {
                e.preventDefault();
                e.stopPropagation();
                if (menu.classList.contains('d-none')) open();
                else close();
            });
        }

        menu.addEventListener('click', e => {
            const item = e.target.closest('[data-provider]');
            if (!item || item.disabled) return;
            e.preventDefault();
            container.dataset.aiProvider = item.dataset.provider;
            render();
            close();
            if (main) main.click();
        });
    }

    /** Initialise every split control found under root (defaults to the document). */
    function initSplits(root) {
        (root || document).querySelectorAll('[data-ai-split]').forEach(initSplit);
    }

    document.addEventListener('click', () => closeAllMenus());

    window.AIProviders = {
        getProviders: getProviders,
        getDefault: getDefault,
        getProvider: getProvider,
        populateSelect: populateSelect,
        selected: selected,
        initSplits: initSplits,
    };
})();
