(function() {
  var LEGACY_SELECT_CLASSES = {
    'custom-select': true,
    'cv-select-base': true,
    'form-select': true,
    'form-select-sm': true,
    'oficios-sort-select': true,
    'searchable-select-native': true,
    'termo-context-select': true
  };
  var currentOpenPicker = null;

  function toArray(list) {
    return Array.prototype.slice.call(list || []);
  }

  function normalizeText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function isPlaceholderText(value) {
    var text = normalizeText(value);
    return !text || /^-+$/.test(text) || /^selecione(?:\.\.\.)?$/i.test(text);
  }

  function stripLegacySelectState(select) {
    if (!select || !select.classList) {
      return;
    }

    var keptClasses = toArray(select.classList).filter(function(name) {
      return !LEGACY_SELECT_CLASSES[name];
    });

    select.className = keptClasses.join(' ');
    select.removeAttribute('style');
    select.removeAttribute('data-searchable-select');
    select.removeAttribute('data-searchable-placeholder');
  }

  function shouldSkipSelect(select) {
    if (!(select instanceof HTMLSelectElement)) {
      return true;
    }
    if (select.hasAttribute('data-oficio-picker-skip') || select.closest('[data-oficio-picker-skip]')) {
      return true;
    }
    if (select.classList.contains('d-none') && !select.closest('.oficio-custeio-picker, .app-select-picker')) {
      return true;
    }
    return false;
  }

  function getSelectPlaceholder(select) {
    var explicit = normalizeText(select.getAttribute('data-oficio-picker-placeholder'));
    if (explicit) {
      return explicit;
    }

    var blankOption = toArray(select.options).find(function(option) {
      return option.value === '';
    });
    if (blankOption) {
      var blankText = normalizeText(blankOption.textContent);
      if (blankText && !isPlaceholderText(blankText)) {
        return blankText;
      }
    }

    return 'Selecione';
  }

  function getOptionDisplay(option, placeholder) {
    var text = normalizeText(option && option.textContent);
    return isPlaceholderText(text) ? placeholder : text;
  }

  function countVisibleOptions(select) {
    return toArray(select && select.options).filter(function(option) {
      return option && !option.hidden;
    }).length;
  }

  function isSearchEnabled(select) {
    var explicit = normalizeText(select && select.getAttribute('data-oficio-picker-search')).toLowerCase();
    if (explicit === 'false' || explicit === 'off' || explicit === '0') {
      return false;
    }
    if (explicit === 'true' || explicit === 'on' || explicit === '1' || explicit === 'always') {
      return true;
    }
    return !!(select && (select.multiple || countVisibleOptions(select) > 8));
  }

  function getSearchPlaceholder(select) {
    var explicit = normalizeText(select && select.getAttribute('data-oficio-picker-search-placeholder'));
    return explicit || 'Digite para filtrar...';
  }

  function syncFormReset(form) {
    if (!form || form.__oficioPickerResetBound) {
      return;
    }

    form.__oficioPickerResetBound = true;
    form.addEventListener('reset', function() {
      window.setTimeout(function() {
        enhanceWithin(form);
        refreshWithin(form);
      }, 0);
    });
  }

  function Picker(select) {
    this.select = select;
    this.wrapper = null;
    this.trigger = null;
    this.label = null;
    this.icon = null;
    this.portal = null;
    this.list = null;
    this.searchContainer = null;
    this.searchInput = null;
    this.optionsHost = null;
    this.activeOptionIndex = -1;
    this.observer = null;
    this.searchTerm = '';
    this.portalAttached = false;
    this.boundSyncPortalPosition = this.syncPortalPosition.bind(this);

    this.build();
    this.bind();
    this.refresh();
  }

  Picker.prototype.build = function() {
    var wrapper = this.select.parentElement && this.select.parentElement.classList.contains('oficio-custeio-picker')
      ? this.select.parentElement
      : null;

    if (!wrapper) {
      wrapper = document.createElement('div');
      wrapper.className = 'app-select-picker oficio-custeio-picker';
      wrapper.setAttribute('data-select-picker', '1');
      this.select.parentNode.insertBefore(wrapper, this.select);
      wrapper.appendChild(this.select);
    } else {
      wrapper.classList.add('app-select-picker');
      wrapper.setAttribute('data-select-picker', '1');
    }

    toArray(wrapper.children).forEach(function(child) {
      if (child !== this.select) {
        child.remove();
      }
    }, this);

    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'app-select-picker__trigger oficio-custeio-picker-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');

    var label = document.createElement('span');
    label.className = 'app-select-picker__label oficio-custeio-picker-label';
    label.textContent = getSelectPlaceholder(this.select);

    var icon = document.createElement('span');
    icon.className = 'app-select-picker__icon oficio-custeio-picker-icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = '▾';

    var list = document.createElement('div');
    list.className = 'app-select-picker__list oficio-custeio-picker-list';
    list.setAttribute('role', 'listbox');
    list.hidden = true;

    var portal = document.createElement('div');
    portal.className = 'app-select-picker__portal oficio-custeio-picker-portal';
    portal.hidden = true;

    var searchContainer = document.createElement('div');
    searchContainer.className = 'app-select-picker__search oficio-custeio-picker-search';
    searchContainer.hidden = true;

    var searchInput = document.createElement('input');
    searchInput.type = 'search';
    searchInput.className = 'app-select-picker__search-input oficio-custeio-picker-search-input';
    searchInput.autocomplete = 'off';
    searchInput.spellcheck = false;
    searchInput.placeholder = getSearchPlaceholder(this.select);

    var optionsHost = document.createElement('div');
    optionsHost.className = 'app-select-picker__options oficio-custeio-picker-options';

    searchContainer.appendChild(searchInput);
    list.appendChild(searchContainer);
    list.appendChild(optionsHost);

    trigger.appendChild(label);
    trigger.appendChild(icon);
    wrapper.appendChild(trigger);
    portal.appendChild(list);
    document.body.appendChild(portal);

    stripLegacySelectState(this.select);
    this.select.classList.add('d-none');

    this.wrapper = wrapper;
    this.trigger = trigger;
    this.label = label;
    this.icon = icon;
    this.portal = portal;
    this.list = list;
    this.searchContainer = searchContainer;
    this.searchInput = searchInput;
    this.optionsHost = optionsHost;
  };

  Picker.prototype.bind = function() {
    var self = this;

    this.trigger.addEventListener('click', function() {
      if (self.isOpen()) {
        self.close(true);
        return;
      }
      self.open(true);
    });

    this.trigger.addEventListener('keydown', function(event) {
      if (self.trigger.disabled) {
        return;
      }

      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (!self.isOpen()) {
          self.open(true);
          return;
        }
        self.moveActive(event.key === 'ArrowDown' ? 1 : -1);
        return;
      }

      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        if (!self.isOpen()) {
          self.open(true);
        } else {
          self.commitActive();
        }
        return;
      }

      if (event.key === 'Escape') {
        self.close(true);
      }
    });

    this.list.addEventListener('mousedown', function(event) {
      if (event.target.closest('[data-oficio-picker-option]')) {
        event.preventDefault();
      }
    });

    this.list.addEventListener('click', function(event) {
      var optionButton = event.target.closest('[data-oficio-picker-option]');
      if (!optionButton) {
        return;
      }
      self.selectOption(parseInt(optionButton.getAttribute('data-oficio-picker-option'), 10));
    });

    this.list.addEventListener('keydown', function(event) {
      if (self.searchContainer && self.searchContainer.contains(event.target)) {
        return;
      }

      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        self.moveActive(event.key === 'ArrowDown' ? 1 : -1);
        return;
      }

      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        self.commitActive();
        return;
      }

      if (event.key === 'Escape') {
        event.preventDefault();
        self.close(true);
        return;
      }

      if (event.key === 'Tab') {
        self.close(false);
      }
    });

    this.searchInput.addEventListener('input', function() {
      self.searchTerm = self.searchInput.value || '';
      self.applyFilter();
    });

    this.searchInput.addEventListener('keydown', function(event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        self.moveActive(event.key === 'ArrowDown' ? 1 : -1);
        return;
      }

      if (event.key === 'Enter') {
        event.preventDefault();
        self.commitActive();
        return;
      }

      if (event.key === 'Escape') {
        event.preventDefault();
        self.close(true);
        return;
      }

      if (event.key === 'Tab') {
        self.close(false);
      }
    });

    this.select.addEventListener('change', function() {
      self.refresh();
    });

    syncFormReset(this.select.form);

    this.observer = new MutationObserver(function() {
      self.refresh();
    });
    this.observer.observe(this.select, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['disabled', 'hidden', 'label', 'selected']
    });
  };

  Picker.prototype.isOpen = function() {
    return this.trigger.getAttribute('aria-expanded') === 'true';
  };

  Picker.prototype.isSearchable = function() {
    return this.wrapper.getAttribute('data-searchable') === 'true';
  };

  Picker.prototype.getVisibleButtons = function() {
    return toArray(this.optionsHost.querySelectorAll('[data-oficio-picker-option]')).filter(function(button) {
      return !button.hidden;
    });
  };

  Picker.prototype.getEnabledButtons = function() {
    return this.getVisibleButtons().filter(function(button) {
      return !button.disabled;
    });
  };

  Picker.prototype.getSelectedOptions = function() {
    return toArray(this.select.options).filter(function(option) {
      return option.selected && !option.hidden;
    });
  };

  Picker.prototype.getDefaultActiveIndex = function() {
    var visibleIndices = this.getVisibleButtons().map(function(button) {
      return parseInt(button.getAttribute('data-oficio-picker-option'), 10);
    });
    var selectedOptions = this.getSelectedOptions();
    var visibleSelected = selectedOptions.find(function(option) {
      return visibleIndices.indexOf(option.index) >= 0;
    });
    if (visibleSelected) {
      return visibleSelected.index;
    }

    var firstEnabled = this.getEnabledButtons()[0];
    if (!firstEnabled) {
      return -1;
    }
    return parseInt(firstEnabled.getAttribute('data-oficio-picker-option'), 10);
  };

  Picker.prototype.updateLabel = function() {
    var placeholder = getSelectPlaceholder(this.select);
    var selectedOptions = this.getSelectedOptions();
    var labelText = placeholder;

    if (this.select.multiple) {
      if (selectedOptions.length === 1) {
        labelText = getOptionDisplay(selectedOptions[0], placeholder);
      } else if (selectedOptions.length === 2) {
        labelText = selectedOptions.map(function(option) {
          return getOptionDisplay(option, placeholder);
        }).join(', ');
      } else if (selectedOptions.length > 2) {
        labelText = selectedOptions.length + ' selecionados';
      }
    } else {
      var selectedOption = this.select.options[this.select.selectedIndex] || null;
      labelText = selectedOption ? getOptionDisplay(selectedOption, placeholder) : placeholder;
    }

    this.label.textContent = labelText || placeholder;
  };

  Picker.prototype.renderOptions = function() {
    var placeholder = getSelectPlaceholder(this.select);
    var hasOptions = false;
    var searchable = isSearchEnabled(this.select);
    var self = this;

    this.wrapper.setAttribute('data-searchable', searchable ? 'true' : 'false');
    this.searchContainer.hidden = !searchable;
    this.searchInput.placeholder = getSearchPlaceholder(this.select);
    this.optionsHost.innerHTML = '';

    if (this.select.multiple) {
      this.list.setAttribute('aria-multiselectable', 'true');
    } else {
      this.list.removeAttribute('aria-multiselectable');
    }

    toArray(this.select.options).forEach(function(option, optionIndex) {
      if (option.hidden) {
        return;
      }

      hasOptions = true;
      var button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('role', 'option');
      button.className = 'app-select-picker__option';
      button.setAttribute('data-oficio-picker-option', String(optionIndex));
      button.setAttribute('aria-selected', option.selected ? 'true' : 'false');
      button.disabled = !!option.disabled;
      button.tabIndex = -1;
      button.textContent = getOptionDisplay(option, placeholder);
      button.setAttribute('data-search-text', normalizeText(button.textContent).toLowerCase());
      self.optionsHost.appendChild(button);
    });

    if (!hasOptions) {
      var empty = document.createElement('div');
      empty.setAttribute('data-empty', 'true');
      empty.textContent = 'Nenhuma opção disponível';
      this.optionsHost.appendChild(empty);
      this.activeOptionIndex = -1;
      return;
    }

    if (!searchable) {
      this.searchTerm = '';
      this.searchInput.value = '';
    }

    this.applyFilter();
  };

  Picker.prototype.applyActiveState = function(shouldFocus) {
    var buttons = toArray(this.optionsHost.querySelectorAll('[data-oficio-picker-option]'));
    var activeButton = null;

    buttons.forEach(function(button) {
      var isActive = !button.hidden && parseInt(button.getAttribute('data-oficio-picker-option'), 10) === this.activeOptionIndex;
      button.toggleAttribute('data-active', isActive);
      button.tabIndex = isActive ? 0 : -1;
      if (isActive) {
        activeButton = button;
      }
    }, this);

    if (shouldFocus && activeButton) {
      activeButton.focus({ preventScroll: true });
      activeButton.scrollIntoView({ block: 'nearest' });
    }
  };

  Picker.prototype.applyFilter = function() {
    var term = normalizeText(this.searchTerm).toLowerCase();
    var buttons = toArray(this.optionsHost.querySelectorAll('[data-oficio-picker-option]'));
    var visibleCount = 0;
    var emptyState = this.optionsHost.querySelector('[data-empty="true"]');

    buttons.forEach(function(button) {
      var matches = !term || button.getAttribute('data-search-text').indexOf(term) >= 0;
      button.hidden = !matches;
      if (matches) {
        visibleCount += 1;
      }
    });

    if (!buttons.length) {
      return;
    }

    if (!visibleCount) {
      if (!emptyState) {
        emptyState = document.createElement('div');
        emptyState.setAttribute('data-empty', 'true');
        this.optionsHost.appendChild(emptyState);
      }
      emptyState.textContent = term ? 'Nenhuma opção encontrada.' : 'Nenhuma opção disponível';
      this.activeOptionIndex = -1;
      return;
    }

    if (emptyState) {
      emptyState.remove();
    }

    if (!this.getVisibleButtons().some(function(button) {
      return parseInt(button.getAttribute('data-oficio-picker-option'), 10) === this.activeOptionIndex;
    }, this)) {
      this.activeOptionIndex = this.getDefaultActiveIndex();
    }

    this.applyActiveState(false);
  };

  Picker.prototype.moveActive = function(step) {
    var enabledButtons = this.getEnabledButtons();
    if (!enabledButtons.length) {
      return;
    }

    var indices = enabledButtons.map(function(button) {
      return parseInt(button.getAttribute('data-oficio-picker-option'), 10);
    });
    var currentPosition = indices.indexOf(this.activeOptionIndex);
    if (currentPosition < 0) {
      currentPosition = 0;
    } else {
      currentPosition = (currentPosition + step + indices.length) % indices.length;
    }

    this.activeOptionIndex = indices[currentPosition];
    this.applyActiveState(true);
  };

  Picker.prototype.open = function(focusSelected) {
    if (this.trigger.disabled) {
      return;
    }

    if (currentOpenPicker && currentOpenPicker !== this) {
      currentOpenPicker.close(false);
    }

    currentOpenPicker = this;
    this.renderOptions();
    this.trigger.setAttribute('aria-expanded', 'true');
    this.list.hidden = false;
    this.portal.hidden = false;
    this.wrapper.setAttribute('data-open', 'true');
    this.portalAttached = true;
    this.syncPortalPosition();
    window.addEventListener('resize', this.boundSyncPortalPosition);
    window.addEventListener('scroll', this.boundSyncPortalPosition, true);

    if (focusSelected) {
      this.activeOptionIndex = this.getDefaultActiveIndex();
      if (this.isSearchable()) {
        this.searchInput.focus({ preventScroll: true });
        if (this.searchInput.value) {
          this.searchInput.select();
        }
        this.applyActiveState(false);
      } else {
        this.applyActiveState(true);
      }
    }

    window.requestAnimationFrame(this.boundSyncPortalPosition);
  };

  Picker.prototype.close = function(returnFocus) {
    this.trigger.setAttribute('aria-expanded', 'false');
    this.list.hidden = true;
    this.portal.hidden = true;
    this.wrapper.removeAttribute('data-open');
    this.portalAttached = false;
    window.removeEventListener('resize', this.boundSyncPortalPosition);
    window.removeEventListener('scroll', this.boundSyncPortalPosition, true);
    if (this.searchTerm) {
      this.searchTerm = '';
      this.searchInput.value = '';
      this.applyFilter();
    }

    if (currentOpenPicker === this) {
      currentOpenPicker = null;
    }

    if (returnFocus) {
      this.trigger.focus({ preventScroll: true });
    }
  };

  Picker.prototype.syncPortalPosition = function() {
    if (!this.portalAttached || this.portal.hidden) {
      return;
    }

    var rect = this.trigger.getBoundingClientRect();
    var gutter = 12;
    var gap = 6;
    var viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
    var viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    var width = Math.min(Math.max(rect.width, 220), Math.max(220, viewportWidth - gutter * 2));
    var left = Math.min(Math.max(rect.left, gutter), Math.max(gutter, viewportWidth - width - gutter));
    var spaceBelow = Math.max(120, viewportHeight - rect.bottom - gutter - gap);
    var spaceAbove = Math.max(120, rect.top - gutter - gap);
    var openUpward = spaceBelow < 240 && spaceAbove > spaceBelow;
    var maxHeight = Math.min(420, openUpward ? spaceAbove : spaceBelow);

    this.portal.style.left = left + 'px';
    this.portal.style.width = width + 'px';
    this.portal.style.zIndex = '1400';
    this.list.style.maxHeight = maxHeight + 'px';

    if (openUpward) {
      this.portal.style.top = 'auto';
      this.portal.style.bottom = Math.max(gutter, viewportHeight - rect.top + gap) + 'px';
    } else {
      this.portal.style.bottom = 'auto';
      this.portal.style.top = Math.min(viewportHeight - gutter, rect.bottom + gap) + 'px';
    }
  };

  Picker.prototype.selectOption = function(optionIndex) {
    var option = this.select.options[optionIndex];
    if (!option || option.disabled) {
      return;
    }

    if (this.select.multiple) {
      option.selected = !option.selected;
      this.activeOptionIndex = optionIndex;
      this.select.dispatchEvent(new Event('change', { bubbles: true }));
      if (this.isSearchable()) {
        this.searchInput.focus({ preventScroll: true });
      } else {
        this.applyActiveState(true);
      }
      return;
    }

    if (this.select.selectedIndex !== optionIndex) {
      this.select.selectedIndex = optionIndex;
      this.select.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
      this.refresh();
    }

    this.close(true);
  };

  Picker.prototype.commitActive = function() {
    if (this.activeOptionIndex < 0) {
      return;
    }
    this.selectOption(this.activeOptionIndex);
  };

  Picker.prototype.refresh = function() {
    stripLegacySelectState(this.select);
    this.select.classList.add('d-none');

    this.wrapper.setAttribute('data-disabled', this.select.disabled ? 'true' : 'false');
    this.wrapper.setAttribute('data-invalid', this.select.classList.contains('is-invalid') ? 'true' : 'false');
    this.trigger.disabled = !!this.select.disabled;

    if (this.select.disabled && this.isOpen()) {
      this.close(false);
    }

    this.updateLabel();
    this.renderOptions();
  };

  function enhanceSelect(select) {
    stripLegacySelectState(select);
    if (shouldSkipSelect(select)) {
      return null;
    }
    if (select.__oficioPicker) {
      select.__oficioPicker.refresh();
      return select.__oficioPicker;
    }

    var picker = new Picker(select);
    select.__oficioPicker = picker;
    return picker;
  }

  function enhanceWithin(root) {
    if (!root) {
      return;
    }

    if (root instanceof HTMLSelectElement) {
      enhanceSelect(root);
      return;
    }

    if (root.querySelectorAll) {
      if (root instanceof Element && root.matches('select')) {
        enhanceSelect(root);
      }
      toArray(root.querySelectorAll('select')).forEach(enhanceSelect);
    }
  }

  function refreshWithin(root) {
    if (!root) {
      return;
    }

    if (root instanceof HTMLSelectElement && root.__oficioPicker) {
      root.__oficioPicker.refresh();
      return;
    }

    if (root.querySelectorAll) {
      var selects = root instanceof Element && root.matches('select')
        ? [root]
        : toArray(root.querySelectorAll('select'));

      selects.forEach(function(select) {
        if (select.__oficioPicker) {
          select.__oficioPicker.refresh();
          return;
        }
        enhanceSelect(select);
      });
    }
  }

  function handleMutations(mutations) {
    mutations.forEach(function(mutation) {
      if (mutation.type === 'childList') {
        toArray(mutation.addedNodes).forEach(function(node) {
          if (node.nodeType === 1) {
            enhanceWithin(node);
          }
        });

        if (mutation.target instanceof HTMLSelectElement) {
          refreshWithin(mutation.target);
        }
        return;
      }

      if (mutation.target instanceof HTMLSelectElement) {
        refreshWithin(mutation.target);
        return;
      }

      if (mutation.target instanceof HTMLOptionElement) {
        var owner = mutation.target.parentElement;
        if (owner instanceof HTMLSelectElement) {
          refreshWithin(owner);
        }
      }
    });
  }

  document.addEventListener('click', function(event) {
    if (
      currentOpenPicker &&
      !currentOpenPicker.wrapper.contains(event.target) &&
      !currentOpenPicker.portal.contains(event.target)
    ) {
      currentOpenPicker.close(false);
    }
  });

  document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape' && currentOpenPicker) {
      currentOpenPicker.close(true);
    }
  });

  window.OficioSelectPicker = {
    enhance: enhanceSelect,
    enhanceWithin: enhanceWithin,
    refresh: refreshWithin
  };
  window.AppSelectPicker = {
    enhance: enhanceSelect,
    enhanceWithin: enhanceWithin,
    refresh: refreshWithin
  };

  function init() {
    enhanceWithin(document);

    var observer = new MutationObserver(handleMutations);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['disabled', 'hidden', 'label', 'selected']
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
