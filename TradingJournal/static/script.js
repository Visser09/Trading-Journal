console.log("Custom script loaded.");

// Show/hide the Edit Day Record form (if you still use day.html)
function toggleEditForm() {
  var form = document.getElementById('editForm');
  if (form) {
    form.style.display = (form.style.display === 'none' || form.style.display === '') ? 'block' : 'none';
  }
}

// Toggle "Add Trade" form on day_multi.html
function toggleAddTradeForm() {
  const form = document.getElementById('addTradeForm');
  if (!form) return;
  form.style.display = (form.style.display === 'none' || form.style.display === '') ? 'block' : 'none';
}

// Toggle "Edit Trade" form for a specific trade on day_multi.html
function toggleEditTradeForm(tradeId) {
  const form = document.getElementById(`editTradeForm_${tradeId}`);
  if (!form) return;
  form.style.display = (form.style.display === 'none' || form.style.display === '') ? 'block' : 'none';
}

function toggleAccountEdit() {
  const accountDisplay = document.getElementById('accountDisplay');
  const accountEdit = document.getElementById('accountEdit');
  if (accountEdit.style.display === 'none' || accountEdit.style.display === '') {
    accountEdit.style.display = 'block';
    accountDisplay.style.display = 'none';
  } else {
    accountEdit.style.display = 'none';
    accountDisplay.style.display = 'block';
  }
}

function toggleSidebar() {
  const sidebar = document.querySelector('.sidebar');
  if (sidebar.style.display === 'block') {
    sidebar.style.display = 'none';
  } else {
    sidebar.style.display = 'block';
  }
}



// QUICK ENTRY: Additional screenshot
let screenshotCountQE = 1;
function addScreenshotFieldQE() {
  const container = document.getElementById('screenshotsContainerQE');
  const newRow = document.createElement('div');
  newRow.classList.add('form-row');

  const newLabel = document.createElement('label');
  newLabel.textContent = "Screenshots:";

  const newInput = document.createElement('input');
  newInput.type = 'file';
  newInput.name = 'screenshots[]';
  newInput.accept = 'image/*';
  newInput.id = `screenshots_qe_${screenshotCountQE}`;

  screenshotCountQE++;

  newRow.appendChild(newLabel);
  newRow.appendChild(newInput);
  container.parentNode.insertBefore(newRow, container.nextSibling);
}

// QUICK ENTRY: Additional scale row
let scaleIndexQE = 1;
function addScaleRowQE() {
  const container = document.getElementById("scaleContainerQE");
  const newRow = document.createElement("div");
  newRow.classList.add("form-row");

  const labelPrice = document.createElement("label");
  labelPrice.textContent = "Scale Price:";
  const inputPrice = document.createElement("input");
  inputPrice.type = "number";
  inputPrice.name = `scale_${scaleIndexQE}_price`;
  inputPrice.step = "any";
  inputPrice.placeholder = "e.g. 12000.25";

  const labelContracts = document.createElement("label");
  labelContracts.textContent = "Contracts:";
  const inputContracts = document.createElement("input");
  inputContracts.type = "number";
  inputContracts.name = `scale_${scaleIndexQE}_contracts`;
  inputContracts.placeholder = "e.g. 1";

  newRow.appendChild(labelPrice);
  newRow.appendChild(inputPrice);
  newRow.appendChild(labelContracts);
  newRow.appendChild(inputContracts);

  container.parentNode.insertBefore(newRow, container.nextSibling);
  scaleIndexQE++;
}

// DAY_MULTI: Additional screenshot for the "Add Trade" form
let screenshotCountTrade = 1;
function addScreenshotFieldTrade() {
  const container = document.getElementById('screenshotsContainerTrade');
  const newRow = document.createElement('div');
  newRow.classList.add('form-row');

  const newLabel = document.createElement('label');
  newLabel.textContent = "Screenshots:";

  const newInput = document.createElement('input');
  newInput.type = 'file';
  newInput.name = 'screenshots[]';
  newInput.accept = 'image/*';
  newInput.id = `screenshots_trade_${screenshotCountTrade}`;

  screenshotCountTrade++;

  newRow.appendChild(newLabel);
  newRow.appendChild(newInput);
  container.parentNode.insertBefore(newRow, container.nextSibling);
}

// DAY_MULTI: Additional scale row for the "Add Trade" form
let scaleIndex = 1;
function addScaleRow() {
  const container = document.getElementById("scaleContainer");
  const newRow = document.createElement("div");
  newRow.classList.add("form-row");

  const labelPrice = document.createElement("label");
  labelPrice.textContent = "Scale Price:";
  const inputPrice = document.createElement("input");
  inputPrice.type = "number";
  inputPrice.name = `scale_${scaleIndex}_price`;
  inputPrice.step = "any";
  inputPrice.placeholder = "e.g. 12000.25";

  const labelContracts = document.createElement("label");
  labelContracts.textContent = "Contracts:";
  const inputContracts = document.createElement("input");
  inputContracts.type = "number";
  inputContracts.name = `scale_${scaleIndex}_contracts`;
  inputContracts.placeholder = "e.g. 1";

  newRow.appendChild(labelPrice);
  newRow.appendChild(inputPrice);
  newRow.appendChild(labelContracts);
  newRow.appendChild(inputContracts);

  container.parentNode.insertBefore(newRow, container.nextSibling);
  scaleIndex++;
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/static/service-worker.js')
      .then(registration => {
        console.log('Service Worker registered with scope: ', registration.scope);
      })
      .catch(error => {
        console.log('Service Worker registration failed: ', error);
      });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const toggles = document.querySelectorAll('.widget-toggle');
  
  // Load saved preferences
  toggles.forEach(toggle => {
    const widgetId = toggle.getAttribute('data-widget');
    const stored = localStorage.getItem(widgetId);
    if (stored !== null) {
      toggle.checked = stored === 'true';
      document.getElementById(widgetId).style.display = toggle.checked ? 'block' : 'none';
    }
  });
  
  toggles.forEach(toggle => {
    toggle.addEventListener('change', (e) => {
      const widgetId = e.target.getAttribute('data-widget');
      const widgetElement = document.getElementById(widgetId);
      if (e.target.checked) {
        widgetElement.style.display = 'block';
      } else {
        widgetElement.style.display = 'none';
      }
      // Save preference
      localStorage.setItem(widgetId, e.target.checked);
    });
  });
});

function toggleWidgetDropdown() {
  const dropdown = document.getElementById('widgetDropdown');
  if (dropdown.style.display === 'block') {
    dropdown.style.display = 'none';
  } else {
    dropdown.style.display = 'block';
  }
}

// Run after DOM loads
document.addEventListener('DOMContentLoaded', () => {
  const toggles = document.querySelectorAll('.widget-toggle');

  // Load saved preferences
  toggles.forEach(toggle => {
    const widgetId = toggle.getAttribute('data-widget');
    const stored = localStorage.getItem(widgetId);
    const widgetEl = document.getElementById(widgetId);

    // If we have a saved preference, use it; otherwise default to checked
    if (stored !== null) {
      toggle.checked = (stored === 'true');
      widgetEl.style.display = toggle.checked ? 'block' : 'none';
    } else {
      // default to checked (visible)
      widgetEl.style.display = 'block';
    }
  });

  // Add event listeners for toggles
  toggles.forEach(toggle => {
    toggle.addEventListener('change', (e) => {
      const widgetId = e.target.getAttribute('data-widget');
      const widgetEl = document.getElementById(widgetId);
      if (e.target.checked) {
        widgetEl.style.display = 'block';
      } else {
        widgetEl.style.display = 'none';
      }
      // Save preference
      localStorage.setItem(widgetId, e.target.checked);
    });
  });
});
