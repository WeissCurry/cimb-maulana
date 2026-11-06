document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  var isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hasGSAP = typeof window.gsap !== 'undefined' && !isReducedMotion;
  var activeOpener = null;

  function openDialog(dialog, opener) {
    if (!dialog || typeof dialog.showModal !== 'function') {
      return false;
    }
    activeOpener = opener || null;
    document.documentElement.classList.add('is-locked');

    if (!dialog.open) {
      dialog.showModal();
    }

    var content = dialog.querySelector('.dialog__content');
    if (hasGSAP && content) {
      window.gsap.fromTo(
        content,
        { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.22, ease: 'power2.out', clearProps: 'transform' }
      );
    }
    return true;
  }

  function closeDialog(dialog) {
    if (!dialog) return;

    function finishClose() {
      if (dialog.open) {
        dialog.close();
      }
      if (!document.querySelector('dialog[open]')) {
        document.documentElement.classList.remove('is-locked');
      }
      var currentUrl = new URL(window.location.href);
      if (currentUrl.searchParams.has('task')) {
        currentUrl.searchParams.delete('task');
        window.history.replaceState(null, '', currentUrl.toString());
      }
      if (activeOpener && typeof activeOpener.focus === 'function') {
        try {
          activeOpener.focus();
        } catch (e) {
          // Ignore focus errors if the element was detached.
        }
        activeOpener = null;
      }
    }

    var content = dialog.querySelector('.dialog__content');
    if (hasGSAP && content && dialog.open) {
      window.gsap.to(content, {
        opacity: 0,
        y: 12,
        duration: 0.16,
        ease: 'power1.in',
        onComplete: function () {
          finishClose();
          window.gsap.set(content, { clearProps: 'all' });
        }
      });
    } else {
      finishClose();
    }
  }

  document.addEventListener('click', function (event) {
    var createTrigger = event.target.closest('[data-open-dialog]');
    if (createTrigger) {
      var targetId = createTrigger.getAttribute('data-open-dialog');
      var targetDialog = document.getElementById(targetId);
      if (targetDialog && openDialog(targetDialog, createTrigger)) {
        event.preventDefault();
      }
      return;
    }

    var taskTrigger = event.target.closest('[data-open-task]');
    if (taskTrigger) {
      // Allow default browser behavior for modifier clicks.
      if (event.ctrlKey || event.metaKey || event.shiftKey) {
        return;
      }
      var taskId = taskTrigger.getAttribute('data-open-task');
      var taskDialog = document.getElementById('task-' + taskId);
      if (taskDialog && openDialog(taskDialog, taskTrigger)) {
        event.preventDefault();
        var currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set('task', taskId);
        window.history.replaceState(null, '', currentUrl.toString());
      }
      return;
    }

    var closeTrigger = event.target.closest('[data-close-dialog]');
    if (closeTrigger) {
      event.preventDefault();
      var parentDialog = closeTrigger.closest('dialog');
      if (parentDialog) {
        closeDialog(parentDialog);
      }
      return;
    }
  });

  // Backdrop clicks target the dialog element itself.
  var allDialogs = document.querySelectorAll('dialog');
  allDialogs.forEach(function (dlg) {
    dlg.addEventListener('click', function (event) {
      if (event.target === dlg) {
        closeDialog(dlg);
      }
    });

    dlg.addEventListener('close', function () {
      if (!document.querySelector('dialog[open]')) {
        document.documentElement.classList.remove('is-locked');
      }
      var currentUrl = new URL(window.location.href);
      if (currentUrl.searchParams.has('task')) {
        currentUrl.searchParams.delete('task');
        window.history.replaceState(null, '', currentUrl.toString());
      }
      if (activeOpener && typeof activeOpener.focus === 'function') {
        try {
          activeOpener.focus();
        } catch (e) {}
        activeOpener = null;
      }
    });
  });

  var autoOpenDialog = document.querySelector('dialog[data-autoopen]');
  var urlParams = new URLSearchParams(window.location.search);
  var taskIdFromUrl = urlParams.get('task');

  if (autoOpenDialog) {
    openDialog(autoOpenDialog, null);
  } else if (taskIdFromUrl) {
    var taskDialog = document.getElementById('task-' + taskIdFromUrl);
    if (taskDialog) {
      openDialog(taskDialog, null);
    }
  }

  function updateCalendarTop() {
    var cal = document.querySelector('.calendar-desktop-view');
    if (cal) {
      var top = cal.getBoundingClientRect().top + (window.scrollY || window.pageYOffset || 0);
      if (top > 0) {
        document.documentElement.style.setProperty('--cal-top', Math.round(top) + 'px');
      }
    }
  }

  updateCalendarTop();
  window.addEventListener('resize', updateCalendarTop);
  window.addEventListener('load', updateCalendarTop);

  var viewTabs = document.querySelectorAll('.view-tabs [data-view]');
  viewTabs.forEach(function (tab) {
    tab.addEventListener('click', function (event) {
      if (event.ctrlKey || event.metaKey || event.shiftKey) {
        return;
      }

      var targetView = tab.getAttribute('data-view');
      var targetPanel = document.getElementById('view-' + targetView);
      if (!targetPanel) {
        return;
      }

      event.preventDefault();
      var currentPanel = document.querySelector('.view-panel.is-active');

      viewTabs.forEach(function (t) {
        t.setAttribute('aria-selected', t.getAttribute('data-view') === targetView ? 'true' : 'false');
      });

      // Preserve the active view in priority filter links.
      var priorityLinks = document.querySelectorAll('.filter-row a');
      priorityLinks.forEach(function (link) {
        try {
          var linkUrl = new URL(link.getAttribute('href'), window.location.origin);
          linkUrl.searchParams.set('view', targetView);
          link.setAttribute('href', linkUrl.pathname + linkUrl.search);
        } catch (err) {}
      });

      if (currentPanel === targetPanel) {
        return;
      }

      function activateTargetPanel() {
        if (currentPanel) {
          currentPanel.classList.remove('is-active');
          currentPanel.style.opacity = '';
        }
        targetPanel.classList.add('is-active');

        if (targetView === 'calendar') {
          updateCalendarTop();
        }

        if (hasGSAP) {
          window.gsap.fromTo(
            targetPanel,
            { opacity: 0, y: 8 },
            {
              opacity: 1,
              y: 0,
              duration: 0.22,
              clearProps: 'all',
              onComplete: function () {
                if (targetView === 'calendar') {
                  updateCalendarTop();
                }
              }
            }
          );

          var cards = targetPanel.querySelectorAll('.card--task, .agenda-day, .undated-item, .list-row, .calendar-day');
          if (cards.length > 0) {
            window.gsap.fromTo(
              Array.from(cards).slice(0, 12),
              { opacity: 0, y: 10 },
              { opacity: 1, y: 0, stagger: 0.03, duration: 0.18, clearProps: 'all' }
            );
          }
        }
      }

      if (hasGSAP && currentPanel) {
        window.gsap.to(currentPanel, {
          opacity: 0,
          duration: 0.14,
          onComplete: activateTargetPanel
        });
      } else {
        activateTargetPanel();
      }

      var currentUrl = new URL(window.location.href);
      currentUrl.searchParams.set('view', targetView);
      window.history.replaceState(null, '', currentUrl.toString());
    });
  });

  // -------------------------------------------------------------------------
  // 3. Kerangka Pemuatan Tampilan Aktif (Loading Skeletons)
  // -------------------------------------------------------------------------
  function showActiveViewSkeleton() {
    var activePanel = document.querySelector('.view-panel.is-active');
    if (!activePanel) {
      return;
    }
    var viewName = activePanel.id ? activePanel.id.replace('view-', '') : '';
    activePanel.setAttribute('aria-busy', 'true');
    activePanel.innerHTML = '';

    if (viewName) {
      var tpl = document.getElementById('skeleton-' + viewName);
      if (tpl) {
        activePanel.appendChild(tpl.content.cloneNode(true));
      }
    }

    // Pastikan terdapat role=status 'Memuat...' di dalam skeleton yang diinjeksi
    if (!activePanel.querySelector('[role="status"]')) {
      var statusSpan = document.createElement('span');
      statusSpan.className = 'sr-only';
      statusSpan.setAttribute('role', 'status');
      statusSpan.textContent = 'Memuat...';
      activePanel.insertBefore(statusSpan, activePanel.firstChild);
    }
  }

  // Tampilkan skeleton saat mengklik filter prioritas atau tautan navigasi bulan kalender
  document.addEventListener('click', function (event) {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey) {
      return;
    }

    var priorityLink = event.target.closest('a[href*="priority="]');
    if (priorityLink && !priorityLink.hasAttribute('data-view') && !priorityLink.closest('[data-view]')) {
      showActiveViewSkeleton();
      return;
    }

    var monthLink = event.target.closest('.calendar-header__nav a, .calendar-agenda-nav a, a[href*="month="]');
    if (monthLink) {
      showActiveViewSkeleton();
      return;
    }
  });

  // Delegasi submit pada form tambah, ubah, pindah, hapus
  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (form && typeof form.checkValidity === 'function' && !form.checkValidity()) {
      return;
    }
    showActiveViewSkeleton();
  });

  // -------------------------------------------------------------------------
  // 4. Status Pemuatan Formulir (Submit Loading State)
  // -------------------------------------------------------------------------
  var allForms = document.querySelectorAll('form:not(.delete-form)');
  allForms.forEach(function (form) {
    form.addEventListener('submit', function () {
      if (typeof form.checkValidity === 'function' && !form.checkValidity()) {
        return;
      }
      showActiveViewSkeleton();
      var submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.setAttribute('aria-busy', 'true');
        submitBtn.textContent = 'Menyimpan...';
        setTimeout(function () {
          submitBtn.disabled = true;
        }, 0);
      }
    });
  });

  // Status loading tombol hapus permanen
  var deleteForms = document.querySelectorAll('.delete-form');
  deleteForms.forEach(function (form) {
    form.addEventListener('submit', function () {
      showActiveViewSkeleton();
      var btn = form.querySelector('.btn-delete');
      if (btn) {
        btn.setAttribute('aria-busy', 'true');
        btn.textContent = 'Menyimpan...';
        setTimeout(function () {
          btn.disabled = true;
        }, 0);
      }
    });
  });

  if (hasGSAP) {
    document.addEventListener('pointerdown', function (event) {
      var btn = event.target.closest('.btn');
      if (btn && !btn.disabled) {
        window.gsap.to(btn, {
          scale: 0.97,
          duration: 0.08,
          yoyo: true,
          repeat: 1,
          ease: 'power1.out',
          clearProps: 'transform'
        });
      }
    });

    var flashItems = document.querySelectorAll('.flash');
    if (flashItems.length > 0) {
      window.gsap.from(flashItems, {
        y: -16,
        opacity: 0,
        stagger: 0.06,
        duration: 0.25,
        ease: 'power2.out',
        clearProps: 'all'
      });
    }
  }

  var isFinePointer = window.matchMedia('(pointer: fine)').matches;
  if (isFinePointer) {
    var taskCards = document.querySelectorAll('.card--task[draggable="true"]');
    var columns = document.querySelectorAll('.board__column[data-stage-key]');

    taskCards.forEach(function (card) {
      card.addEventListener('dragstart', function (event) {
        var taskId = card.getAttribute('data-task-id');
        event.dataTransfer.setData('text/plain', taskId);
        event.dataTransfer.effectAllowed = 'move';
        card.classList.add('is-dragging');
      });

      card.addEventListener('dragend', function () {
        card.classList.remove('is-dragging');
        columns.forEach(function (col) {
          col.classList.remove('is-drop-target');
        });
      });
    });

    columns.forEach(function (column) {
      column.addEventListener('dragover', function (event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        column.classList.add('is-drop-target');
      });

      column.addEventListener('dragleave', function (event) {
        if (!column.contains(event.relatedTarget)) {
          column.classList.remove('is-drop-target');
        }
      });

      column.addEventListener('drop', function (event) {
        event.preventDefault();
        column.classList.remove('is-drop-target');

        var taskId = event.dataTransfer.getData('text/plain');
        var targetStage = column.getAttribute('data-stage-key');

        if (!taskId || !targetStage) {
          return;
        }

        var draggedCard = document.querySelector('.card--task[data-task-id="' + taskId + '"]');
        if (!draggedCard) {
          return;
        }

        var dndForm =
          draggedCard.querySelector('form.form-move--dnd') ||
          draggedCard.querySelector('form.form-move--select') ||
          draggedCard.querySelector('form.form-move');
        if (!dndForm) {
          return;
        }

        var statusInput = dndForm.querySelector('input[name="status"]');
        var statusSelect = dndForm.querySelector('select[name="status"]');

        if (statusInput) {
          statusInput.value = targetStage;
          showActiveViewSkeleton();
          dndForm.submit();
        } else if (statusSelect) {
          if (statusSelect.value === targetStage) {
            return;
          }
          statusSelect.value = targetStage;
          showActiveViewSkeleton();
          dndForm.submit();
        }
      });
    });
  }

  var stageJumpLinks = document.querySelectorAll('[data-stage-jump]');
  var boardWrapper = document.querySelector('.board-wrapper');
  if (stageJumpLinks.length > 0 && boardWrapper) {
    stageJumpLinks.forEach(function (link) {
      link.addEventListener('click', function (event) {
        var key = link.getAttribute('data-stage-jump');
        var targetCol = document.getElementById('col-' + key);
        if (targetCol) {
          event.preventDefault();
          targetCol.scrollIntoView({ behavior: 'smooth', inline: 'start', block: 'nearest' });
        }
      });
    });
  }

  document.addEventListener('click', function (event) {
    var dayBtn = event.target.closest('.cal-day-cell');
    if (!dayBtn) return;

    var dayKey = dayBtn.getAttribute('data-day');
    if (!dayKey) return;

    var tpl = document.querySelector('template[data-day="' + dayKey + '"]');
    var container = document.getElementById('cal-selected-day-container');
    if (tpl && container) {
      container.innerHTML = '';
      container.appendChild(tpl.content.cloneNode(true));

      document.querySelectorAll('.cal-day-cell').forEach(function (btn) {
        var isThis = btn.getAttribute('data-day') === dayKey;
        btn.setAttribute('aria-pressed', isThis ? 'true' : 'false');
        if (isThis) {
          btn.classList.add('is-selected');
        } else {
          btn.classList.remove('is-selected');
        }
      });

      if (hasGSAP) {
        window.gsap.fromTo(
          container,
          { opacity: 0, y: 4 },
          { opacity: 1, y: 0, duration: 0.16, ease: 'power1.out', clearProps: 'all' }
        );
      }
    }
  });
});
