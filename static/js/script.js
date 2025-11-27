// NEMSU CCMS - Main JavaScript File

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    const popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert && alert.classList.contains('alert-dismissible')) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    });

    // Form validation enhancements
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="loading me-2"></span> Processing...';
            }
        });
    });

    // Password strength checker
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(input => {
        input.addEventListener('input', function() {
            const strengthIndicator = this.parentNode.querySelector('.password-strength');
            if (strengthIndicator) {
                const password = this.value;
                let strength = 0;

                if (password.length >= 8) strength++;
                if (password.match(/[a-z]/) && password.match(/[A-Z]/)) strength++;
                if (password.match(/\d/)) strength++;
                if (password.match(/[^a-zA-Z\d]/)) strength++;

                const strengthText = ['Very Weak', 'Weak', 'Medium', 'Strong', 'Very Strong'];
                const strengthColors = ['danger', 'warning', 'info', 'primary', 'success'];

                strengthIndicator.textContent = strengthText[strength];
                strengthIndicator.className = `badge bg-${strengthColors[strength]} password-strength`;
            }
        });
    });

    // Character counter for textareas
    const textareas = document.querySelectorAll('textarea[maxlength]');
    textareas.forEach(textarea => {
        const maxLength = textarea.getAttribute('maxlength');
        const counter = document.createElement('div');
        counter.className = 'form-text text-end';
        counter.textContent = `0/${maxLength} characters`;

        textarea.parentNode.appendChild(counter);

        textarea.addEventListener('input', function() {
            const currentLength = this.value.length;
            counter.textContent = `${currentLength}/${maxLength} characters`;

            if (currentLength > maxLength * 0.9) {
                counter.classList.add('text-warning');
            } else {
                counter.classList.remove('text-warning');
            }
        });
    });

    // File upload preview
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            const preview = this.parentNode.querySelector('.file-preview');
            if (preview && this.files.length > 0) {
                const file = this.files[0];
                if (file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        preview.innerHTML = `<img src="${e.target.result}" class="img-thumbnail mt-2" style="max-height: 200px;">`;
                    };
                    reader.readAsDataURL(file);
                } else {
                    preview.innerHTML = `<div class="alert alert-info mt-2">
                        <i class="fas fa-file me-2"></i>${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)
                    </div>`;
                }
            }
        });
    });

    // Auto-hide success messages after action
    const successMessages = document.querySelectorAll('.alert-success');
    successMessages.forEach(alert => {
        setTimeout(() => {
            if (alert && alert.classList.contains('alert-dismissible')) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 3000);
    });

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Dynamic page loading indicators
    let isLoading = false;

    document.addEventListener('click', function(e) {
        if (e.target.matches('a') && e.target.href && !e.target.href.includes('#')) {
            const link = e.target;
            if (link.target !== '_blank' && !link.hasAttribute('download')) {
                isLoading = true;
                // You can add a loading spinner here if needed
            }
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl + / to focus search
        if (e.ctrlKey && e.key === '/') {
            e.preventDefault();
            const searchInput = document.querySelector('input[type="search"]');
            if (searchInput) {
                searchInput.focus();
            }
        }

        // Escape to close modals
        if (e.key === 'Escape') {
            const openModal = document.querySelector('.modal.show');
            if (openModal) {
                const modal = bootstrap.Modal.getInstance(openModal);
                if (modal) {
                    modal.hide();
                }
            }
        }
    });

    // Print functionality
    window.printPage = function() {
        window.print();
    };

    // Export functionality (placeholder)
    window.exportData = function(format) {
        alert(`Export functionality for ${format} format would be implemented here.`);
    };

    // Theme switcher (basic)
    window.toggleTheme = function() {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-bs-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-bs-theme', newTheme);

        // Save preference
        localStorage.setItem('theme', newTheme);

        // Update button text
        const themeBtn = document.querySelector('#themeToggle');
        if (themeBtn) {
            themeBtn.innerHTML = newTheme === 'dark' ?
                '<i class="fas fa-sun me-2"></i>Light Mode' :
                '<i class="fas fa-moon me-2"></i>Dark Mode';
        }
    };

    // Load saved theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-bs-theme', savedTheme);
    }

    console.log('NEMSU CCMS JavaScript loaded successfully!');
});

// Utility functions
const CCMS = {
    // Format date
    formatDate: function(dateString) {
        const options = {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        };
        return new Date(dateString).toLocaleDateString('en-PH', options);
    },

    // Truncate text
    truncateText: function(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substr(0, maxLength) + '...';
    },

    // Show notification
    showNotification: function(message, type = 'info') {
        // Implementation for custom notifications
        console.log(`[${type.toUpperCase()}] ${message}`);
    },

    // Validate email
    validateEmail: function(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
};