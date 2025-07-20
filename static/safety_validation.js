
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
        field.addEventListener('blur', function() {
            if (this.value === '0' || this.value === '') {
                this.style.borderColor = '#dc3545';
                this.style.backgroundColor = '#fff5f5';
                
                // Show warning
                const warningMsg = document.createElement('small');
                warningMsg.className = 'text-danger';
                warningMsg.textContent = 'This field cannot be zero - it would cause trading errors';
                
                if (!this.nextElementSibling || !this.nextElementSibling.classList.contains('text-danger')) {
                    this.parentNode.insertBefore(warningMsg, this.nextSibling);
                }
                
                setTimeout(() => {
                    this.style.borderColor = '';
                    this.style.backgroundColor = '';
                    if (warningMsg.parentNode) {
                        warningMsg.parentNode.removeChild(warningMsg);
                    }
                }, 3000);
            }
        });
    }
}

// Initialize safety features when page loads
document.addEventListener('DOMContentLoaded', function() {
    addSafetyTooltips();
    
    // Add zero prevention to critical fields
    const criticalFields = ['margin', 'leverage', 'rsiPeriod', 'macdFast', 'macdSlow', 'assessmentInterval'];
    criticalFields.forEach(fieldId => preventZeroEntry(fieldId));
});
