// Global variables
let currentUser = null;
let isEditing = false;
let currentLeadId = null;
let formData = {};
let bypassUnsavedWarning = false;
const SALES_TYPE_STORAGE_KEY = 'sales_types';

// Initialize add lead page
document.addEventListener('DOMContentLoaded', function () {
    console.log('Add Lead page initializing...');

    // Check authentication
    const userData = localStorage.getItem('user');
    if (userData) {
        currentUser = JSON.parse(userData);
        console.log('User authenticated:', currentUser.username);
    } else {
        console.log('No user found, redirecting to login');
        window.location.href = '/';
        return;
    }
    // View created lead (exposed to inline handlers)
    window.viewCreatedLead = function () {
        bypassUnsavedWarning = true;
        const leadId = window.lastCreatedLeadId;
        if (leadId) {
            // Redirect directly to lead detail page for the newly created lead
            window.location.href = `/lead-detail/${leadId}`;
        } else {
            window.location.href = '/leads';
        }
    };

    // Create another lead (exposed to inline handlers)
    window.createAnotherLead = function () {
        const successModal = document.getElementById('successModal');
        if (successModal) {
            successModal.style.display = 'none';
            document.body.style.overflow = 'auto';
        }

        // Clear form
        const form = document.getElementById('leadForm');
        if (form) {
            form.reset();
        }

        // Clear errors
        document.querySelectorAll('.field-error').forEach(error => error.remove());
        document.querySelectorAll('.error').forEach(field => field.classList.remove('error'));

        // Set default values
        const today = new Date().toISOString().split('T')[0];
        const leadDateInput = document.getElementById('lead_date');
        if (leadDateInput) leadDateInput.value = today;

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };


    // Check permissions
    if (!currentUser.permissions.can_create_leads && !currentUser.permissions.can_edit_leads) {
        alert('You do not have permission to create leads');
        window.location.href = '/dashboard';
        return;
    }

    // Load Lead Settings from database first
    LeadSettingsManager.loadSettings().then(function () {
        console.log('Lead Settings loaded from database');

        // Initialize form
        initializeForm();
        initializeSalesType();

        // Check if editing existing lead
        checkEditMode();

        // Initialize form validation
        initializeValidation();

        // Initialize form data persistence
        initializeFormPersistence();

        // Load industry suggestions
        loadIndustrySuggestions();

        // Initialize address lookup
        initializeAddressLookup();

        console.log('Add Lead page initialized successfully');
    }).catch(function (error) {
        console.error('Failed to load lead settings:', error);
        // Continue with form initialization even if settings fail to load
        initializeForm();
        initializeSalesType();
        checkEditMode();
        initializeValidation();
        initializeFormPersistence();
        loadIndustrySuggestions();
        initializeAddressLookup();
    });
});

// Initialize form
function initializeForm() {
    console.log('Initializing form...');

    // Initialize all dropdowns from Lead Settings
    if (window.LeadSettingsManager) {
        window.LeadSettingsManager.initializeAllDropdowns();
    }

    // Set today's date as default
    const today = new Date().toISOString().split('T')[0];
    const leadDateInput = document.getElementById('lead_date');
    if (leadDateInput) leadDateInput.value = today;
    // Assignee list load
    loadAssignees();

    // Add change listeners for dependent fields
    initializeLocationSelectors();

    // Initialize dependent Sub-Industry dropdown
    initializeSubIndustryDropdown();

    // Add form submission handler
    const leadForm = document.getElementById('leadForm');
    if (leadForm) {
        leadForm.addEventListener('submit', function (e) {
            e.preventDefault();
            saveLead();
        });
    }

    // Add save shortcut (Ctrl + S)
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            saveLead();
        }
    });

    // Add calculate form progress on input
    document.querySelectorAll('input, select, textarea').forEach(element => {
        element.addEventListener('input', calculateFormProgress);
        element.addEventListener('change', calculateFormProgress);
    });

    // Initial progress calculation
    setTimeout(calculateFormProgress, 100);
}

// Load assignees - Auto-assign to current logged-in user only
function loadAssignees() {
    const select = document.getElementById('assigned_to');
    const detailsBox = document.getElementById('assigneeDetails');
    if (!select) return;

    // Check if currentUser is available
    if (!currentUser) {
        console.error('Current user not found');
        select.innerHTML = '<option value="">User not found</option>';
        return;
    }

    // Fetch current user's full details from API to get designation and mobile
    fetch('/api/users/active')
        .then(res => res.ok ? res.json() : null)
        .then(data => {
            if (data?.success && data.users) {
                // Find current logged-in user in the users list
                const currentUserId = currentUser.user_id || currentUser.id;
                const userDetails = data.users.find(u => u.id == currentUserId);

                if (userDetails) {
                    // Update currentUser with full details
                    currentUser.designation = userDetails.designation || '';
                    currentUser.mobile_no = userDetails.mobile_no || '';
                    currentUser.email = userDetails.email || currentUser.email || '';
                }
            }
        })
        .catch(err => console.warn('Could not fetch user details:', err))
        .finally(() => {
            // Create option with current user's data
            select.innerHTML = '';
            const opt = document.createElement('option');
            opt.value = currentUser.user_id || currentUser.id || '';
            opt.textContent = currentUser.full_name || currentUser.username || 'Me';
            opt.dataset.designation = currentUser.designation || '';
            opt.dataset.email = currentUser.email || '';
            opt.dataset.mobile = currentUser.mobile_no || '';
            select.appendChild(opt);

            // Auto-select current user
            select.value = opt.value;

            // Show assignee details automatically
            handleAssigneeChange();

            console.log('Auto-assigned lead to:', currentUser.full_name || currentUser.username);
            console.log('Designation:', currentUser.designation);
            console.log('Mobile:', currentUser.mobile_no);
        });

    select.addEventListener('change', handleAssigneeChange);
}

function handleAssigneeChange() {
    const select = document.getElementById('assigned_to');
    const detailsBox = document.getElementById('assigneeDetails');
    if (!select || !detailsBox) return;

    const option = select.selectedOptions[0];
    if (!option || !option.value) {
        detailsBox.style.display = 'none';
        detailsBox.innerHTML = '';
        const designationInput = document.getElementById('designation');
        if (designationInput) designationInput.value = '';
        return;
    }

    const name = option.textContent;
    const designation = option.dataset.designation || '—';
    const email = option.dataset.email || '—';
    const mobile = option.dataset.mobile || '—';

    // Auto-fill designation field from assignee if available
    const designationInput = document.getElementById('designation');
    if (designationInput) {
        designationInput.value = option.dataset.designation || '';
        designationInput.readOnly = true;
    }

    detailsBox.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:4px; padding:10px; border:1px dashed #dee2e6; border-radius:8px; background:#f8f9fa;">
            <div><strong>${name}</strong></div>
            <div style=\"color:#6c757d;\">Designation: ${designation}</div>
            <div style=\"color:#6c757d;\">Email: ${email}</div>
            <div style=\"color:#6c757d;\">Mobile: ${mobile}</div>
        </div>`;
    detailsBox.style.display = 'block';
}

// Sales type - Now managed by Lead Settings
function initializeSalesType() {
    // This function is now simplified as dropdowns are populated by LeadSettingsManager
    // Just keep the button to open Lead Settings
    const addSalesTypeBtn = document.getElementById('addSalesTypeBtn');
    if (addSalesTypeBtn) {
        // Button already has onclick to open Lead Settings in new tab
        console.log('Sales Type button configured to open Lead Settings');
    }
}

// Calculate form completion progress
function calculateFormProgress() {
    const requiredFields = document.querySelectorAll('[required]');
    if (requiredFields.length === 0) return 0;

    const filledFields = Array.from(requiredFields).filter(field => {
        if (field.type === 'checkbox') return field.checked;
        return field.value.trim() !== '';
    }).length;

    const progress = Math.round((filledFields / requiredFields.length) * 100);

    const progressFill = document.getElementById('formProgress');
    const progressPercent = document.getElementById('progressPercent');

    if (progressFill) {
        progressFill.style.width = progress + '%';
    }

    if (progressPercent) {
        progressPercent.textContent = progress + '%';
    }

    return progress;
}

// Check if editing existing lead
function checkEditMode() {
    const urlParams = new URLSearchParams(window.location.search);
    const leadId = urlParams.get('edit');

    if (leadId) {
        if (!currentUser.permissions.can_edit_leads) {
            alert('You do not have permission to edit leads');
            window.location.href = '/leads';
            return;
        }

        isEditing = true;
        currentLeadId = leadId;
        loadLeadForEditing(leadId);
    }
}

// Load lead for editing
async function loadLeadForEditing(leadId) {
    try {
        showLoading(true);
        const response = await fetch(`/api/leads/${leadId}`, {
            // No Authorization header needed, the session cookie is sent automatically.
        });

        if (!response.ok) {
            if (response.status === 401) {
                localStorage.removeItem('user');
                alert('Session expired. Please login again.');
                window.location.href = '/';
                return;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            populateForm(data.lead);
            updatePageTitle('Edit Lead');
        } else {
            throw new Error(data.detail || 'Failed to load lead');
        }
    } catch (error) {
        console.error('Error loading lead:', error);
        alert('Failed to load lead for editing: ' + error.message);
        window.location.href = '/leads';
    } finally {
        showLoading(false);
    }
}

// Populate form with lead data
function populateForm(lead) {
    console.log('Populating form with lead data:', lead);

    // Helper function to safely set value
    function setValue(id, value) {
        const element = document.getElementById(id);
        if (element && value !== null && value !== undefined) {
            element.value = value;
        }
    }

    // Basic Information
    setValue('lead_date', lead.lead_date);
    setValue('lead_source', lead.lead_source);
    setValue('lead_type', lead.lead_type);
    setValue('assigned_to', lead.assigned_to);
    setValue('designation', lead.designation);

    // Company Information
    setValue('company_name', lead.company_name);
    setValue('industry_type', lead.industry_type);
    // Ensure sub-industry options match selected industry before setting value
    try { updateSubIndustryDropdown(); } catch (_) { }
    // Set sub-industry value, adding option if missing
    const subSelect = document.getElementById('sub_industry');
    if (subSelect && lead.sub_industry) {
        const hasOption = Array.from(subSelect.options).some(o => o.value === lead.sub_industry);
        if (!hasOption) {
            const opt = document.createElement('option');
            opt.value = lead.sub_industry;
            opt.textContent = lead.sub_industry;
            subSelect.appendChild(opt);
        }
    }
    setValue('sub_industry', lead.sub_industry);
    setValue('system', lead.system);
    setValue('project_amc', lead.project_amc);

    // Contact Information
    setValue('customer_name', lead.customer_name);
    setValue('designation_customer', lead.designation_customer);
    setValue('contact_no', lead.contact_no);
    setValue('email_id', lead.email_id);
    setValue('linkedin_profile', lead.linkedin_profile);

    // Address Information (ensure options exist first)
    setLocationValues(lead.state, lead.district, lead.city);
    setValue('pin_code', lead.pin_code);
    setValue('full_address', lead.full_address);

    // Additional Information
    setValue('company_website', lead.company_website);
    setValue('company_linkedin_link', lead.company_linkedin_link);
    setValue('gstin', lead.gstin);

    // Update page title
    document.querySelector('h1 i.fa-user-plus').className = 'fas fa-edit';
    document.querySelector('h1').innerHTML = '<i class="fas fa-edit"></i> Edit Lead';

    // Refresh verification badges for populated URLs / fields
    const companyWebsiteInput = document.getElementById('company_website');
    if (companyWebsiteInput && companyWebsiteInput.value) {
        validateWebsite({ target: companyWebsiteInput });
    }
    const companyLinkedinInput = document.getElementById('company_linkedin_link');
    if (companyLinkedinInput && companyLinkedinInput.value) {
        validateLinkedIn({ target: companyLinkedinInput });
    }
    const gstinInput = document.getElementById('gstin');
    if (gstinInput && gstinInput.value) {
        validateGSTIN({ target: gstinInput });
    }
    const emailInput = document.getElementById('email_id');
    if (emailInput && emailInput.value) {
        validateEmail({ target: emailInput });
    }
    const phoneInput = document.getElementById('contact_no');
    if (phoneInput && phoneInput.value) {
        validatePhone({ target: phoneInput });
    }
    const linkedinInput = document.getElementById('linkedin_profile');
    if (linkedinInput && linkedinInput.value) {
        validateLinkedIn({ target: linkedinInput });
    }
    const pinCodeInput = document.getElementById('pin_code');
    if (pinCodeInput && pinCodeInput.value) {
        const pin = pinCodeInput.value.replace(/\D/g, '');
        if (pin.length === 6) {
            lookupAddressByPinCode(pin);
        }
    }

    // Store original data for comparison
    formData = getFormData();

    // Update form progress
    setTimeout(calculateFormProgress, 100);
}

// Update page title
function updatePageTitle(title) {
    document.title = `${title} - Smart CRM`;
    const header = document.querySelector('.header-left h1');
    if (header) {
        header.innerHTML = `<i class="fas fa-edit"></i> ${title}`;
    }
}

// Initialize form validation
function initializeValidation() {
    const form = document.getElementById('leadForm');
    if (!form) return;

    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');

    inputs.forEach(input => {
        input.addEventListener('blur', validateField);
        input.addEventListener('input', clearFieldError);
    });

    // Add custom validation for email
    const emailInput = document.getElementById('email_id');
    if (emailInput) {
        emailInput.addEventListener('blur', validateEmail);
    }

    // Add custom validation for phone
    const phoneInput = document.getElementById('contact_no');
    if (phoneInput) {
        phoneInput.addEventListener('blur', validatePhone);
    }

    // Add custom validation for website
    const websiteInput = document.getElementById('company_website');
    if (websiteInput) {
        websiteInput.addEventListener('blur', validateWebsite);
    }

    // Add custom validation for LinkedIn (company and contact)
    const linkedinInput = document.getElementById('linkedin_profile');
    if (linkedinInput) {
        linkedinInput.addEventListener('blur', validateLinkedIn);
    }
    const companyLinkedinInput = document.getElementById('company_linkedin_link');
    if (companyLinkedinInput) {
        companyLinkedinInput.addEventListener('blur', validateLinkedIn);
    }

    // Add custom validation for GSTIN
    const gstinInput = document.getElementById('gstin');
    if (gstinInput) {
        gstinInput.addEventListener('blur', validateGSTIN);
    }
}

// Validate field
function validateField(e) {
    const field = e.target;
    const value = field.value.trim();
    const isRequired = field.hasAttribute('required');

    // 🚀 GSTIN ko completely ignore karo
    if (field.id === 'gstin') {
        clearFieldError({ target: field }); // extra safety
        return true;
    }

    if (isRequired && !value) {
        showFieldError(field, 'This field is required');
        return false;
    }

    return true;
}

// Toggle inline verification status elements for company fields
function updateVerificationStatus(fieldId, isValid, message = 'Verified \u2713') {
    const statusEl = document.getElementById(`${fieldId}_status`);
    if (!statusEl) return;

    if (isValid) {
        statusEl.textContent = message;
        statusEl.style.color = '#198754';
        statusEl.style.display = 'block';
    } else {
        statusEl.textContent = '';
        statusEl.style.display = 'none';
    }
}

// Validate email
function validateEmail(e) {
    const field = e.target;
    const email = field.value.trim();
    clearFieldError({ target: field });

    if (!email) return true;

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        updateVerificationStatus(field.id, false);
        showFieldError(field, 'Please enter a valid email address');
        return false;
    }
    const domain = email.split('@')[1] || '';
    const tld = domain.split('.').pop() || '';
    updateVerificationStatus(field.id, true, `Verified \u2713 • Domain: ${domain}${tld ? ' • TLD: ' + tld.toUpperCase() : ''}`);
    return true;
}

// Validate phone
function validatePhone(e) {
    const field = e.target;
    const phone = field.value.trim().replace(/\D/g, '');
    clearFieldError({ target: field });

    if (!phone) return true;

    if (phone.length !== 10) {
        updateVerificationStatus(field.id, false);
        showFieldError(field, 'Please enter a valid 10-digit phone number');
        return false;
    }
    const formatted = `+91-${phone.slice(0, 5)}-${phone.slice(5)}`;
    updateVerificationStatus(field.id, true, `Verified \u2713 • ${formatted}`);
    return true;
}

// Validate website
function validateWebsite(e) {
    const field = e.target;
    const website = field.value.trim();
    clearFieldError({ target: field });

    if (!website) {
        updateVerificationStatus(field.id, false);
        return true;
    }

    try {
        // Add protocol if missing
        const urlToTest = website.startsWith('http') ? website : `https://${website}`;
        const parsed = new URL(urlToTest);

        // Normalize the URL back to the field
        field.value = parsed.href;
        updateVerificationStatus(field.id, true);
        return true;
    } catch (err) {
        // If URL constructor fails, try basic validation
        const urlPattern = /^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9](?:\.[a-zA-Z]{2,})+/;
        if (urlPattern.test(website)) {
            // It's a valid domain, just add https://
            field.value = `https://${website}`;
            updateVerificationStatus(field.id, true);
            return true;
        }

        updateVerificationStatus(field.id, false);
        showFieldError(field, 'Please enter a valid website URL (e.g., example.com or https://example.com)');
        return false;
    }
}

// Validate LinkedIn
function validateLinkedIn(e) {
    const field = e.target;
    const url = field.value.trim();
    clearFieldError({ target: field });

    if (!url) {
        updateVerificationStatus(field.id, false);
        return true;
    }

    if (!url.toLowerCase().includes('linkedin.com')) {
        updateVerificationStatus(field.id, false);
        showFieldError(field, 'Please enter a valid LinkedIn profile URL');
        return false;
    }

    try {
        const parsed = new URL(url.startsWith('http') ? url : `https://${url}`);
        const pathParts = parsed.pathname.split('/').filter(Boolean);
        const segment = pathParts[0] || '';
        const slug = pathParts[1] || segment || 'profile';
        let kind = 'LinkedIn';
        if (segment === 'in') kind = 'Profile';
        else if (segment === 'company') kind = 'Company';
        const message = `Verified \u2713 • ${kind}: ${slug}`;
        updateVerificationStatus(field.id, true, message);
        field.value = parsed.href; // normalize
        return true;
    } catch (err) {
        updateVerificationStatus(field.id, false);
        showFieldError(field, 'Please enter a valid LinkedIn profile URL');
        return false;
    }
}

const GST_STATE_CODES = {
    '01': 'Jammu & Kashmir',
    '02': 'Himachal Pradesh',
    '03': 'Punjab',
    '04': 'Chandigarh',
    '05': 'Uttarakhand',
    '06': 'Haryana',
    '07': 'Delhi',
    '08': 'Rajasthan',
    '09': 'Uttar Pradesh',
    '10': 'Bihar',
    '11': 'Sikkim',
    '12': 'Arunachal Pradesh',
    '13': 'Nagaland',
    '14': 'Manipur',
    '15': 'Mizoram',
    '16': 'Tripura',
    '17': 'Meghalaya',
    '18': 'Assam',
    '19': 'West Bengal',
    '20': 'Jharkhand',
    '21': 'Odisha',
    '22': 'Chhattisgarh',
    '23': 'Madhya Pradesh',
    '24': 'Gujarat',
    '25': 'Daman and Diu',
    '26': 'Dadra and Nagar Haveli',
    '27': 'Maharashtra',
    '28': 'Andhra Pradesh (Old)',
    '29': 'Karnataka',
    '30': 'Goa',
    '31': 'Lakshadweep',
    '32': 'Kerala',
    '33': 'Tamil Nadu',
    '34': 'Puducherry',
    '35': 'Andaman and Nicobar Islands',
    '36': 'Telangana',
    '37': 'Andhra Pradesh',
    '38': 'Ladakh'
};

// Validate GSTIN and surface parsed details
function validateGSTIN(e) {
    const field = e.target;
    let gstin = field.value.trim().toUpperCase();
    field.value = gstin;

    const statusDiv = document.getElementById("gstin_status");

    // ✅ OPTIONAL FIELD — if empty, no error
    if (!gstin) {
        statusDiv.style.display = "none";
        statusDiv.innerText = "";  // 👈 IMPORTANT
        clearFieldError({ target: field }); // 👈 THIS LINE ADD
        return true;
    }
    // Exact 15 characters check
    if (gstin.length !== 15) {
        statusDiv.style.display = "block";
        statusDiv.style.color = "#dc3545";
        statusDiv.innerText = "GSTIN must be exactly 15 characters";
        return false;
    }

    // Regex check
    const gstinRegex = /^[0-9A-Z]{15}$/;
    if (!gstinRegex.test(gstin)) {
        statusDiv.style.display = "block";
        statusDiv.style.color = "#dc3545";
        statusDiv.innerText = "Invalid GSTIN format";
        return false;
    }

    // Valid GSTIN
    statusDiv.style.display = "block";
    statusDiv.style.color = "#198754";
    statusDiv.innerText = "Valid GSTIN ✓";
    return true;
}

function parseGstinDetails(gstin) {
    const stateCode = gstin.slice(0, 2);
    const pan = gstin.slice(2, 12);
    const entity = gstin.slice(12, 13);
    const checksum = gstin.slice(14);
    const stateName = GST_STATE_CODES[stateCode] || 'Unknown State';
    return `Verified \u2713 • State: ${stateName} (${stateCode}) • PAN: ${pan} • Entity: ${entity} • Checksum: ${checksum}`;
}

// Show field error
function showFieldError(field, message) {
    clearFieldError({ target: field });

    const errorDiv = document.createElement('div');
    errorDiv.className = 'field-error';
    errorDiv.textContent = message;

    field.parentNode.appendChild(errorDiv);
    field.classList.add('error');

    // Scroll to error field
    field.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// Clear field error
function clearFieldError(e) {
    const field = e.target;
    const errorDiv = field.parentNode.querySelector('.field-error');

    if (errorDiv) {
        errorDiv.remove();
    }

    field.classList.remove('error');
}

// Load industry suggestions
function loadIndustrySuggestions() {
    const industries = [
        'IT',
        'Manufacturing',
        'Healthcare',
        'Education',
        'Finance',
        'Retail',
        'Real Estate',
        'Hospitality',
        'Logistics',
        'Telecommunications',
        'Media',
        'Construction',
        'Energy',
        'Agriculture',
        'Consulting',
        'Legal',
        'Marketing',
        'Non-Profit',
        'Government',
        'Other'
    ];

    const industrySelect = document.getElementById('industry_type');
    if (industrySelect) {
        // Add options if not already present
        if (industrySelect.options.length <= 1) {
            industries.forEach(industry => {
                if (!Array.from(industrySelect.options).some(opt => opt.value === industry)) {
                    const option = document.createElement('option');
                    option.value = industry;
                    option.textContent = industry;
                    industrySelect.appendChild(option);
                }
            });
        }
    }
}

// Update sub-industry suggestions
// Initialize and wire the dependent Sub-Industry dropdown
function initializeSubIndustryDropdown() {
    const industrySelect = document.getElementById('industry_type');
    const subSelect = document.getElementById('sub_industry');
    if (!industrySelect || !subSelect) return;

    // Default state
    subSelect.innerHTML = '';
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Select Sub-Industry';
    subSelect.appendChild(placeholder);
    subSelect.disabled = true;

    // Update options when industry changes
    industrySelect.addEventListener('change', updateSubIndustryDropdown);

    // Initial population (e.g., after restoring draft or editing)
    setTimeout(updateSubIndustryDropdown, 0);
}

// Populate Sub-Industry options based on selected Industry (from lead settings)
function updateSubIndustryDropdown() {
    const industrySelect = document.getElementById('industry_type');
    const subSelect = document.getElementById('sub_industry');
    if (!industrySelect || !subSelect) return;

    const selectedIndustryName = industrySelect.value;
    subSelect.innerHTML = '';

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Select Sub-Industry';
    subSelect.appendChild(placeholder);

    if (!selectedIndustryName) {
        subSelect.disabled = true;
        subSelect.value = '';
        return;
    }

    // Pull industries from LeadSettingsManager/localStorage
    let industries = [];
    try {
        industries = window.LeadSettingsManager.getSettings('industries') || [];
    } catch (e) {
        try {
            industries = JSON.parse(localStorage.getItem('lead_settings_industries') || '[]');
        } catch (_) { industries = []; }
    }

    // Ensure subIndustries array exists
    industries = industries.map(i => ({ ...i, subIndustries: i.subIndustries || [] }));

    const parent = industries.find(i => i.name === selectedIndustryName);
    const subs = parent ? parent.subIndustries.filter(s => s.active !== false) : [];

    if (subs.length === 0) {
        const noOpt = document.createElement('option');
        noOpt.value = '';
        noOpt.textContent = 'No sub-industries available';
        noOpt.disabled = true;
        subSelect.appendChild(noOpt);
        subSelect.disabled = true;
        subSelect.value = '';
        return;
    }

    subs.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.name;
        opt.textContent = s.name;
        subSelect.appendChild(opt);
    });

    subSelect.disabled = false;

    // Preserve current value if present in options
    const saved = getFormData();
    const currentValue = saved.sub_industry || subSelect.value;
    if (currentValue && Array.from(subSelect.options).some(o => o.value === currentValue)) {
        subSelect.value = currentValue;
    } else {
        subSelect.value = '';
    }
}

// Hierarchical location data (sample set)
const LOCATION_DATA = {
    'Delhi': {
        'New Delhi': ['Chanakyapuri', 'Connaught Place', 'Karol Bagh'],
        'South Delhi': ['Hauz Khas', 'Saket', 'Greater Kailash'],
        'West Delhi': ['Rajouri Garden', 'Janakpuri', 'Dwarka']
    },
    'Maharashtra': {
        'Mumbai': ['Andheri', 'Bandra', 'Powai', 'Thane'],
        'Pune': ['Shivaji Nagar', 'Hinjawadi', 'Kothrud', 'Viman Nagar'],
        'Nagpur': ['Sitabuldi', 'Dharampeth', 'Civil Lines']
    },
    'Karnataka': {
        'Bangalore': ['Whitefield', 'Indiranagar', 'Koramangala', 'HSR Layout'],
        'Mysore': ['Lakshmipuram', 'Jayalakshmipuram', 'Vijayanagar'],
        'Mangalore': ['Bejai', 'Kadri', 'Hampankatta']
    },
    'Tamil Nadu': {
        'Chennai': ['Adyar', 'Velachery', 'T Nagar', 'Anna Nagar'],
        'Coimbatore': ['RS Puram', 'Peelamedu', 'Gandhipuram'],
        'Madurai': ['KK Nagar', 'Anna Nagar', 'Arapalayam']
    },
    'Uttar Pradesh': {
        'Lucknow': ['Gomti Nagar', 'Hazratganj', 'Alambagh'],
        'Kanpur': ['Swaroop Nagar', 'Kakadeo', 'Govind Nagar'],
        'Noida': ['Sector 62', 'Sector 18', 'Sector 128']
    },
    'Gujarat': {
        'Ahmedabad': ['Navrangpura', 'Satellite', 'Maninagar'],
        'Surat': ['Adajan', 'Vesu', 'Katargam'],
        'Vadodara': ['Alkapuri', 'Gotri', 'Manjalpur']
    },
    'West Bengal': {
        'Kolkata': ['Salt Lake', 'Park Street', 'Behala'],
        'Howrah': ['Shibpur', 'Bally', 'Andul'],
        'Durgapur': ['City Center', 'Benachity', 'Bidhan Nagar']
    },
    'Rajasthan': {
        'Jaipur': ['Malviya Nagar', 'Vaishali Nagar', 'Mansarovar'],
        'Jodhpur': ['Ratanada', 'Shastri Nagar', 'Paota'],
        'Udaipur': ['Hiran Magri', 'Fatehpura', 'Bhuwana']
    },
    'Haryana': {
        'Gurgaon': ['DLF Phase 1', 'Sohna Road', 'Cyber City'],
        'Faridabad': ['Sector 15', 'Sector 28', 'Greenfield'],
        'Panipat': ['Model Town', 'Sector 12', 'Huda']
    },
    'Telangana': {
        'Hyderabad': ['Banjara Hills', 'Madhapur', 'Gachibowli'],
        'Warangal': ['Hanamkonda', 'Kazipet', 'Subedari']
    },
    'Kerala': {
        'Kochi': ['Edappally', 'Kadavanthra', 'Fort Kochi'],
        'Thiruvananthapuram': ['Kowdiar', 'Pattom', 'Vellayambalam'],
        'Kozhikode': ['Kallai', 'Beypore', 'West Hill']
    }
};

function initializeLocationSelectors() {
    const stateSelect = document.getElementById('state');
    const districtSelect = document.getElementById('district');
    const citySelect = document.getElementById('city');
    if (!stateSelect || !districtSelect || !citySelect) return;

    renderOptions(stateSelect, Object.keys(LOCATION_DATA), 'Select State');

    stateSelect.addEventListener('change', () => {
        const state = stateSelect.value;
        renderOptions(districtSelect, state ? Object.keys(LOCATION_DATA[state] || {}) : [], 'Select District');
        renderOptions(citySelect, [], 'Select City');
    });

    districtSelect.addEventListener('change', () => {
        const state = stateSelect.value;
        const district = districtSelect.value;
        const cities = state && district ? LOCATION_DATA[state]?.[district] || [] : [];
        renderOptions(citySelect, cities, 'Select City');
    });
}

// Ensure dropdown values are set respecting available options
function setLocationValues(state, district, city) {
    const stateSelect = document.getElementById('state');
    const districtSelect = document.getElementById('district');
    const citySelect = document.getElementById('city');
    if (!stateSelect || !districtSelect || !citySelect) return;

    if (state) {
        const stateExists = Array.from(stateSelect.options).some(opt => opt.value === state);
        if (!stateExists) {
            const opt = document.createElement('option');
            opt.value = state;
            opt.textContent = state;
            stateSelect.appendChild(opt);
        }
        stateSelect.value = state;
        stateSelect.dispatchEvent(new Event('change'));
    }

    if (district) {
        const districtExists = Array.from(districtSelect.options).some(opt => opt.value === district);
        if (!districtExists) {
            const opt = document.createElement('option');
            opt.value = district;
            opt.textContent = district;
            districtSelect.appendChild(opt);
        }
        districtSelect.value = district;
        districtSelect.dispatchEvent(new Event('change'));
    }

    if (city) {
        const optionExists = Array.from(citySelect.options).some(opt => opt.value === city);
        if (!optionExists && citySelect.value === '') {
            const opt = document.createElement('option');
            opt.value = city;
            opt.textContent = city;
            citySelect.appendChild(opt);
        }
        citySelect.value = city;
    }
}

function renderOptions(selectEl, values, placeholder) {
    if (!selectEl) return;
    selectEl.innerHTML = '';
    const ph = document.createElement('option');
    ph.value = '';
    ph.textContent = placeholder;
    selectEl.appendChild(ph);
    values.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        selectEl.appendChild(opt);
    });
}

// Initialize address lookup
function initializeAddressLookup() {
    const pinCodeInput = document.getElementById('pin_code');
    if (!pinCodeInput) return;

    pinCodeInput.addEventListener('blur', function () {
        const pinCode = this.value.replace(/\D/g, '');
        if (pinCode.length === 6) {
            lookupAddressByPinCode(pinCode);
        } else {
            updatePinStatus(false, 'Enter 6-digit PIN code');
        }
    });
}

function populateLocationFromLookup(state, district, city) {
    document.getElementById("state").value = state || "";
    document.getElementById("district").value = district || "";
    document.getElementById("city").value = city || "";
}

// Update status message
function updatePinStatus(isValid, message) {
    const statusDiv = document.getElementById("pin_code_status");
    statusDiv.style.display = "block";
    statusDiv.style.color = isValid ? "#198754" : "#dc3545";
    statusDiv.innerText = message;
}

// Show loading (optional UI)
function showLoading(isLoading) {
    const statusDiv = document.getElementById("pin_code_status");
    if (isLoading) {
        statusDiv.style.display = "block";
        statusDiv.style.color = "#0d6efd";
        statusDiv.innerText = "Looking up PIN code...";
    }
}

// Optional: city mapping if you want custom names
const pinCityMapping = {
    "400077": "Mumbai",
    "110001": "New Delhi",
    "411001": "Pune"
};

async function lookupAddressByPinCode(pinCode) {
    if (pinCode.length !== 6) {
        populateLocationFromLookup("", "", "");
        updatePinStatus(false, "Enter 6-digit PIN code");
        return;
    }

    try {
        showLoading(true);
        const response = await fetch(`https://api.postalpincode.in/pincode/${pinCode}`);
        const data = await response.json();

        if (data[0].Status === 'Success' && data[0].PostOffice.length > 0) {
            const postOffice = data[0].PostOffice[0];

            const state = postOffice.State || '';
            const district = postOffice.District || '';
            const city = postOffice.Block || postOffice.District || ''; // Correct city

            populateLocationFromLookup(state, district, city);
            updatePinStatus(true, `Verified ✓ • ${city}, ${district}, ${state}`);
        } else {
            populateLocationFromLookup("", "", "");
            updatePinStatus(false, 'Invalid PIN code');
        }
    } catch (error) {
        console.error('Address lookup failed:', error);
        populateLocationFromLookup("", "", "");
        updatePinStatus(false, 'Lookup failed');
    }
}


// Event listener for PIN code input
document.getElementById("pin_code").addEventListener("input", function () {
    const pinCode = this.value.trim();
    lookupAddressByPinCode(pinCode);
});
function populateLocationFromLookup(state, district, city) {
    const stateSelect = document.getElementById('state');
    const districtSelect = document.getElementById('district');
    const citySelect = document.getElementById('city');
    if (!stateSelect || !districtSelect || !citySelect) return;

    if (state) {
        const stateExists = Array.from(stateSelect.options).some(opt => opt.value === state);
        if (!stateExists) {
            const opt = document.createElement('option');
            opt.value = state;
            opt.textContent = state;
            stateSelect.appendChild(opt);
        }
        stateSelect.value = state;
        stateSelect.dispatchEvent(new Event('change'));
    }

    if (district) {
        const districtExists = Array.from(districtSelect.options).some(opt => opt.value === district);
        if (!districtExists) {
            const opt = document.createElement('option');
            opt.value = district;
            opt.textContent = district;
            districtSelect.appendChild(opt);
        }
        districtSelect.value = district;
        districtSelect.dispatchEvent(new Event('change'));
    }

    if (city) {
        const optionExists = Array.from(citySelect.options).some(opt => opt.value === city);
        if (!optionExists && citySelect.value === '') {
            const opt = document.createElement('option');
            opt.value = city;
            opt.textContent = city;
            citySelect.appendChild(opt);
        }
        citySelect.value = city;
    }
}

function updatePinStatus(isValid, message = '') {
    const statusEl = document.getElementById('pin_code_status');
    if (!statusEl) return;
    if (isValid) {
        statusEl.textContent = message || 'Verified \u2713';
        statusEl.style.color = '#198754';
        statusEl.style.display = 'block';
    } else {
        statusEl.textContent = message || '';
        statusEl.style.color = '#dc3545';
        statusEl.style.display = message ? 'block' : 'none';
    }
}

// Initialize form persistence
function initializeFormPersistence() {
    if (isEditing) return; // Don't save drafts when editing

    const form = document.getElementById('leadForm');
    if (!form) return;

    // Load saved data
    const savedData = localStorage.getItem('lead_form_draft');
    if (savedData) {
        try {
            const data = JSON.parse(savedData);
            Object.keys(data).forEach(key => {
                const input = document.getElementById(key);
                if (input && input.type !== 'file') {
                    input.value = data[key];
                }
            });

            // Show restore notification
            setTimeout(() => {
                if (confirm('You have a saved draft. Would you like to restore it?')) {
                    showNotification('Draft restored', 'success');
                } else {
                    clearFormDraft();
                }
            }, 500);
        } catch (error) {
            console.log('Failed to load draft:', error);
        }
    }

    // Save data on input (with debounce)
    let saveTimeout;
    form.addEventListener('input', () => {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(saveFormDraft, 2000);
    });

    // Clear draft on successful save
    window.addEventListener('beforeunload', function (e) {
        if (bypassUnsavedWarning) return;
        const hasUnsavedChanges = JSON.stringify(getFormData()) !== JSON.stringify(formData);
        if (hasUnsavedChanges) {
            saveFormDraft();
            // Show warning
            e.preventDefault();
            e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
        }
    });
}

// Save form draft
function saveFormDraft() {
    const formData = getFormData();
    localStorage.setItem('lead_form_draft', JSON.stringify(formData));
    console.log('Form draft saved');
}

// Clear form draft
function clearFormDraft() {
    localStorage.removeItem('lead_form_draft');
    console.log('Form draft cleared');
}

// Get form data
function getFormData() {
    const form = document.getElementById('leadForm');
    if (!form) return {};

    const formData = new FormData(form);
    const data = {};

    formData.forEach((value, key) => {
        data[key] = value;
    });

    // Normalize assigned_to to integer when possible
    if (data.assigned_to) {
        const num = Number(data.assigned_to);
        if (!Number.isNaN(num)) data.assigned_to = num;
    }

    return data;
}

// Validate form
function validateForm() {
    const form = document.getElementById('leadForm');
    if (!form) return false;

    const requiredInputs = form.querySelectorAll('[required]');
    let isValid = true;

    // Clear all errors first
    form.querySelectorAll('.field-error').forEach(error => error.remove());
    form.querySelectorAll('.error').forEach(field => field.classList.remove('error'));

    // Validate required fields
    requiredInputs.forEach(input => {
        const value = input.value.trim();

        if (!value) {
            showFieldError(input, 'This field is required');
            isValid = false;
        }
    });

    // Validate email
    const emailInput = document.getElementById('email_id');
    if (emailInput && emailInput.value.trim()) {
        const emailResult = validateEmail({ target: emailInput });
        if (!emailResult) {
            isValid = false;
        }
    }

    // Validate phone
    const phoneInput = document.getElementById('contact_no');
    if (phoneInput && phoneInput.value.trim()) {
        const phoneResult = validatePhone({ target: phoneInput });
        if (!phoneResult) {
            isValid = false;
        }
    }

    // Validate website
    const websiteInput = document.getElementById('company_website');
    if (websiteInput && websiteInput.value.trim()) {
        const websiteResult = validateWebsite({ target: websiteInput });
        if (!websiteResult) {
            isValid = false;
        }
    }

    // Validate LinkedIn
    const linkedinInput = document.getElementById('linkedin_profile');
    if (linkedinInput && linkedinInput.value.trim()) {
        const linkedinResult = validateLinkedIn({ target: linkedinInput });
        if (!linkedinResult) {
            isValid = false;
        }
    }

    // Validate GSTIN
    const gstinInput = document.getElementById('gstin');
    if (gstinInput && gstinInput.value.trim()) {
        const gstinResult = validateGSTIN({ target: gstinInput });
        if (!gstinResult) {
            isValid = false;
        }
    }

    return isValid;
}

// Save lead
async function saveLead() {
    console.log('Saving lead...');

    if (!validateForm()) {
        showNotification('Please fix the errors in the form', 'error');
        return;
    }

    const formData = getFormData();

    try {
        showLoading(true);

        const url = isEditing ? `/api/leads/${currentLeadId}` : '/api/leads';
        const method = isEditing ? 'PUT' : 'POST';

        console.log('Sending request to:', url, 'Method:', method);

        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        console.log('Response status:', response.status);

        if (!response.ok) {
            if (response.status === 401) {
                // Clear stored credentials and redirect to login
                localStorage.removeItem('user');
                alert('Session expired. Please login again.');
                window.location.href = '/';
                return;
            }

            let errorMessage = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorMessage;
            } catch (e) {
                // Could not parse error response
            }
            throw new Error(errorMessage);
        }

        const data = await response.json();
        console.log('Response data:', data);

        if (data.success) {
            // Clear form draft
            clearFormDraft();

            if (isEditing) {
                showSuccessModal('Lead updated successfully!', data.lead_id || currentLeadId);
            } else {
                showSuccessModal('Lead created successfully!', data.lead_id);
            }
        } else {
            throw new Error(data.detail || 'Failed to save lead');
        }
    } catch (error) {
        console.error('Error saving lead:', error);
        showNotification(`Failed to save lead: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

// Show success modal
function showSuccessModal(message, leadId) {
    console.log('Showing success modal for lead:', leadId);

    const successMessage = document.getElementById('successMessage');
    const generatedLeadId = document.getElementById('generatedLeadId');
    const successCompanyName = document.getElementById('successCompanyName');
    const successContactName = document.getElementById('successContactName');

    if (successMessage) successMessage.textContent = message;
    if (generatedLeadId) generatedLeadId.textContent = leadId;

    // Set company and contact names from form
    const companyName = document.getElementById('company_name')?.value;
    const customerName = document.getElementById('customer_name')?.value;

    if (successCompanyName && companyName) successCompanyName.textContent = companyName;
    if (successContactName && customerName) successContactName.textContent = customerName;

    // Store lead ID for viewing
    window.lastCreatedLeadId = leadId;

    // Show modal
    const successModal = document.getElementById('successModal');
    if (successModal) {
        successModal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

// View new lead
function viewNewLead() {
    const leadId = window.lastCreatedLeadId;
    if (leadId) {
        // Redirect directly to lead detail page for the newly created lead
        window.location.href = `/lead-detail/${leadId}`;
    } else {
        window.location.href = '/leads';
    }
}

// Add another lead
function addAnotherLead() {
    clearForm();
    closeModal('successModal');
}

// Clear form
function clearForm() {
    if (confirm('Are you sure you want to clear the form? All unsaved changes will be lost.')) {
        const form = document.getElementById('leadForm');
        if (form) {
            form.reset();
        }

        // Clear errors
        document.querySelectorAll('.field-error').forEach(error => error.remove());
        document.querySelectorAll('.error').forEach(field => field.classList.remove('error'));

        // Set default values
        const today = new Date().toISOString().split('T')[0];
        const leadDateInput = document.getElementById('lead_date');
        if (leadDateInput) leadDateInput.value = today;

        const leadOwnerInput = document.getElementById('leadOwner');
        if (leadOwnerInput && currentUser) {
            leadOwnerInput.value = currentUser.full_name || 'Sales Executive';
        }

        // Clear form draft
        clearFormDraft();

        // Update progress
        setTimeout(calculateFormProgress, 100);

        // Focus on first field
        if (leadDateInput) leadDateInput.focus();

        showNotification('Form cleared successfully', 'success');
    }
}

// Save and add another
function saveAndAddAnother() {
    // Override success behavior
    const originalSuccessModal = window.showSuccessModal;

    window.showSuccessModal = function (message, leadId) {
        // Don't show modal, just clear form and show notification
        closeModal('successModal');
        clearForm();
        showNotification(message + ' (ID: ' + leadId + ')', 'success');
        window.showSuccessModal = originalSuccessModal;
    };

    saveLead();
}

// Close modal
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

// Show loading
function showLoading(show) {
    const loadingOverlay = document.getElementById('loadingOverlay');
    const saveBtn = document.getElementById('saveBtn');
    const saveAnotherBtn = document.getElementById('saveAnotherBtn');

    if (loadingOverlay) {
        loadingOverlay.style.display = show ? 'flex' : 'none';
    }

    if (saveBtn) saveBtn.disabled = show;
    if (saveAnotherBtn) saveAnotherBtn.disabled = show;
}

// Show notification
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' :
            type === 'error' ? 'exclamation-circle' :
                type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
        <span>${message}</span>
        <button onclick="this.parentElement.remove()">×</button>
    `;

    // Add styles if not already present
    if (!document.getElementById('notification-styles')) {
        const styles = document.createElement('style');
        styles.id = 'notification-styles';
        styles.textContent = `
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                border-radius: 10px;
                display: flex;
                align-items: center;
                gap: 10px;
                z-index: 9999;
                animation: slideIn 0.3s ease;
                max-width: 400px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                color: white;
            }
            .notification.success {
                background: linear-gradient(135deg, #10b981, #059669);
            }
            .notification.error {
                background: linear-gradient(135deg, #ef4444, #dc2626);
            }
            .notification.warning {
                background: linear-gradient(135deg, #f59e0b, #d97706);
            }
            .notification.info {
                background: linear-gradient(135deg, #3b82f6, #1d4ed8);
            }
            .notification i {
                font-size: 18px;
            }
            .notification button {
                background: none;
                border: none;
                color: white;
                font-size: 20px;
                cursor: pointer;
                padding: 0;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
                margin-left: auto;
            }
            .notification button:hover {
                background: rgba(255,255,255,0.2);
            }
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        `;
        document.head.appendChild(styles);
    }

    document.body.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Add additional CSS for field errors
if (!document.getElementById('add-lead-styles')) {
    const styles = document.createElement('style');
    styles.id = 'add-lead-styles';
    styles.textContent = `
        .field-error {
            color: #ef4444;
            font-size: 12px;
            margin-top: 5px;
            animation: slideDown 0.3s ease;
        }
        input.error, select.error, textarea.error {
            border-color: #ef4444 !important;
            background-color: #fef2f2 !important;
        }
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(5px);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
        .loading-content {
            text-align: center;
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            border: 2px solid #3b82f6;
        }
        .loading-spinner {
            width: 50px;
            height: 50px;
            border: 5px solid #f3f3f3;
            border-top: 5px solid #3b82f6;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        .loading-text {
            color: #1e40af;
            font-weight: 600;
            font-size: 16px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(styles);
}

// Close modals when clicking outside or pressing Escape
document.addEventListener('click', function (event) {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        if (event.target === modal) {
            closeModal(modal.id);
        }
    });
});

document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        closeModal('successModal');
    }
});

console.log('Add Lead JavaScript loaded successfully');