
// Safety Validation UI Handler
function handleSafetyValidation(response) {
    if (response.safety_warnings && Object.keys(response.safety_warnings).length > 0) {
        // Create safety warning panel
        const warningPanel = document.createElement('div');
        warningPanel.className = 'alert alert-warning mt-3';
        warningPanel.innerHTML = `
            <h6><i class="fas fa-shield-alt"></i> Safety Validation Applied</h6>
            <p>Some values were automatically corrected to prevent trading errors:</p>
            <ul>
                ${Object.entries(response.safety_warnings).map(([param, message]) => 
                    `<li><strong>${param}:</strong> ${message}</li>`
                ).join('')}
            </ul>
            <small class="text-muted">These safety checks protect your bot from configuration errors that could cause trading failures.</small>
        `;
        
        // Insert warning panel after the form
        const form = document.querySelector('.config-form');
        if (form) {
            form.parentNode.insertBefore(warningPanel, form.nextSibling);
            
            // Auto-remove after 10 seconds
            setTimeout(() => {
                if (warningPanel.parentNode) {
                    warningPanel.parentNode.removeChild(warningPanel);
                }
            }, 10000);
        }
    }
}

// Add safety tooltips to form inputs
function addSafetyTooltips() {
    const safetyTips = {
        'margin': 'Cannot be zero - this would prevent any trading. Standard: 50 USDT',
        'leverage': 'Cannot be zero - this would make position size zero. Safe: 5x',
        'rsiPeriod': 'Cannot be zero - this would break RSI calculation. Standard: 14',
        'macdFast': 'Cannot be zero - this would break MACD calculation. Standard: 12',
        'macdSlow': 'Cannot be zero - this would break MACD calculation. Standard: 26',
        'assessmentInterval': 'Cannot be zero - bot would never check markets. Standard: 60 seconds',
        'cooldownPeriod': 'Cannot be zero - could cause rapid fire trading. Safe: 300 seconds'
    };
    
    Object.entries(safetyTips).forEach(([fieldId, tip]) => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.setAttribute('title', tip);
            field.setAttribute('data-toggle', 'tooltip');
            field.setAttribute('data-placement', 'top');
        }
    });
    
    // Initialize Bootstrap tooltips if available
    if (typeof $ !== 'undefined' && $.fn.tooltip) {
        $('[data-toggle="tooltip"]').tooltip();
    }
}

// Prevent zero entry on critical fields
function preventZeroEntry(fieldId) {
    const field = document.getElementById(fieldId);
    if (field) {
        let hasError = false;
        let errorMessage = null;
        
        field.addEventListener('blur', function() {
            if (this.value === '0' || this.value === '') {
                hasError = true;
                this.style.borderColor = '#dc3545';
                this.style.backgroundColor = '#fff5f5';
                
                // Show warning
                errorMessage = document.createElement('small');
                errorMessage.className = 'text-danger';
                errorMessage.textContent = 'This field cannot be zero - it would cause trading errors';
                
                if (!this.nextElementSibling || !this.nextElementSibling.classList.contains('text-danger')) {
                    this.parentNode.insertBefore(errorMessage, this.nextSibling);
                }
                
                // Disable save button
                disableSaveButton();
                
            } else if (hasError) {
                // Clear error state when valid value is entered
                hasError = false;
                this.style.borderColor = '';
                this.style.backgroundColor = '';
                
                if (errorMessage && errorMessage.parentNode) {
                    errorMessage.parentNode.removeChild(errorMessage);
                    errorMessage = null;
                }
                
                // Re-enable save button if no other errors exist
                enableSaveButtonIfValid();
            }
        });
        
        // Also check on input change for immediate feedback
        field.addEventListener('input', function() {
            if (hasError && this.value !== '0' && this.value !== '') {
                hasError = false;
                this.style.borderColor = '';
                this.style.backgroundColor = '';
                
                if (errorMessage && errorMessage.parentNode) {
                    errorMessage.parentNode.removeChild(errorMessage);
                    errorMessage = null;
                }
                
                enableSaveButtonIfValid();
            }
        });
    }
}

// Function to disable save button
function disableSaveButton() {
    const saveButtons = document.querySelectorAll('button[type="submit"], .btn-success, .save-btn');
    saveButtons.forEach(btn => {
        btn.disabled = true;
        btn.classList.add('disabled');
    });
}

// Function to enable save button if no validation errors exist
function enableSaveButtonIfValid() {
    // Check if there are any remaining validation errors
    const errorElements = document.querySelectorAll('.text-danger');
    const fieldsWithErrors = document.querySelectorAll('input[style*="border-color: rgb(220, 53, 69)"]');
    
    if (errorElements.length === 0 && fieldsWithErrors.length === 0) {
        const saveButtons = document.querySelectorAll('button[type="submit"], .btn-success, .save-btn');
        saveButtons.forEach(btn => {
            btn.disabled = false;
            btn.classList.remove('disabled');
        });
    }
}

// Initialize safety features when page loads
document.addEventListener('DOMContentLoaded', function() {
    addSafetyTooltips();
    
    // Add zero prevention to critical fields
    const criticalFields = ['margin', 'leverage', 'rsiPeriod', 'macdFast', 'macdSlow', 'assessmentInterval'];
    criticalFields.forEach(fieldId => preventZeroEntry(fieldId));
    
    // Add form submission handler to validate before submit
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const hasErrors = validateFormBeforeSubmit();
            if (hasErrors) {
                e.preventDefault();
                showValidationAlert('Please fix the validation errors before saving.');
                return false;
            }
        });
    });
});

// Validate entire form before submission
function validateFormBeforeSubmit() {
    const criticalFields = ['margin', 'leverage', 'rsiPeriod', 'macdFast', 'macdSlow', 'assessmentInterval'];
    let hasErrors = false;
    
    criticalFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field && (field.value === '0' || field.value === '')) {
            hasErrors = true;
            // Trigger the validation display
            field.dispatchEvent(new Event('blur'));
        }
    });
    
    return hasErrors;
}

// Show validation alert
function showValidationAlert(message) {
    // Remove existing alerts
    const existingAlerts = document.querySelectorAll('.validation-alert');
    existingAlerts.forEach(alert => alert.remove());
    
    // Create new alert
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger validation-alert mt-3';
    alert.innerHTML = `
        <i class="fas fa-exclamation-triangle"></i>
        <strong>Validation Error:</strong> ${message}
    `;
    
    // Insert at top of form
    const form = document.querySelector('form');
    if (form) {
        form.insertBefore(alert, form.firstChild);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, 5000);
    }
}
