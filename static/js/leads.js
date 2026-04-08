// Leads Management JavaScript
// leads.js
const currentUser = {
    user_id: {{ user.user_id|default (0) }},
username: "{{ user.username|default('') }}",
    full_name: "{{ user.full_name|default('') }}",
        email: "{{ user.email|default('') }}",
            role: "{{ user.role|default('') }}",
                permissions: {
    can_view_leads: { { user.permissions.can_view_leads |default (false) | lower } },
    can_create_leads: { { user.permissions.can_create_leads |default (false) | lower } },
    can_edit_leads: { { user.permissions.can_edit_leads |default (false) | lower } },
    can_delete_leads: { { user.permissions.can_delete_leads |default (false) | lower } },
    can_view_users: { { user.permissions.can_view_users |default (false) | lower } },
    can_manage_users: { { user.permissions.can_manage_users |default (false) | lower } },
    can_view_reports: { { user.permissions.can_view_reports |default (false) | lower } },
    can_export_data: { { user.permissions.can_export_data |default (false) | lower } }
}
};

// Session validation on page load
async function validateSessionOnLoad() {
    try {
        const response = await fetch('/api/validate-session', { credentials: 'include' });
        if (!response.ok) { window.location.href = '/login'; return false; }
        const data = await response.json();
        if (data.success) return true;
        window.location.href = '/login';
        return false;
    } catch (error) {
        console.error('Session validation error:', error);
        window.location.href = '/login';
        return false;
    }
}

document.addEventListener('DOMContentLoaded', async function () {
    const isValidSession = await validateSessionOnLoad();
    if (!isValidSession) return;

    if (window.LeadSettingsManager) {
        await LeadSettingsManager.loadSettings();
    }

    initializeLeadsPage();
    loadLeads();
    setCurrentDate();
    setupEventListeners();
});

// Global variables
let currentPage = 1;
let totalPages = 1;
let pageSize = 20;
let currentFilters = {};
let selectedLeadId = null;
let currentLeadData = null;

// Initialize leads page
function initializeLeadsPage() {
    if (window.LeadSettingsManager) {
        window.LeadSettingsManager.initializeAllDropdowns();
    }

    const today = new Date().toISOString().split('T')[0];
    document.getElementById('date-to').max = today;
    document.getElementById('date-from').max = today;

    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    document.getElementById('date-from').value = thirtyDaysAgo.toISOString().split('T')[0];
    document.getElementById('date-to').value = today;

    // ===== READ URL PARAMS FIRST =====
    const urlParams = new URLSearchParams(window.location.search);
    const filterParam = urlParams.get('filter');
    const statusParam = urlParams.get('status');

    // Initialize base filters
    currentFilters = {
        status: '',
        source: '',
        dateFrom: document.getElementById('date-from').value,
        dateTo: document.getElementById('date-to').value,
        search: '',
        missedFollowups: false
    };

    // If missed filter — set it and clear everything else
    if (filterParam === 'missed') {
        currentFilters.missedFollowups = true;
        currentFilters.status = '';
        currentFilters.search = '';
        // Clear dropdowns so they don't interfere
        const statusDropdown = document.getElementById('status-filter');
        if (statusDropdown) statusDropdown.value = '';
        setTimeout(showMissedFollowupsBanner, 100);
        return; // ← EXIT EARLY, don't process statusParam
    }

    // Only apply status param if NOT missed filter
    if (statusParam) {
        const statusDropdown = document.getElementById('status-filter');
        if (statusDropdown) {
            statusDropdown.value = statusParam;
            currentFilters.status = statusParam;
        }
    }
}

// ===== MISSED FOLLOW-UPS BANNER =====
function showMissedFollowupsBanner() {
    if (document.getElementById('missed-filter-banner')) return;

    if (!document.getElementById('missed-banner-anim')) {
        const styleEl = document.createElement('style');
        styleEl.id = 'missed-banner-anim';
        styleEl.textContent = `
            @keyframes slideDown {
                from { opacity: 0; transform: translateY(-10px); }
                to   { opacity: 1; transform: translateY(0); }
            }
        `;
        document.head.appendChild(styleEl);
    }

    const banner = document.createElement('div');
    banner.id = 'missed-filter-banner';
    banner.style.cssText = `
        background: #fef2f2;
        border: 1px solid #fca5a5;
        border-radius: 10px;
        padding: 12px 18px;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        color: #dc2626;
        font-size: 0.9rem;
        box-shadow: 0 2px 8px rgba(239,68,68,0.1);
        animation: slideDown 0.3s ease;
    `;
    banner.innerHTML = `
        <span style="display:flex; align-items:center; gap:8px;">
            <i class="fas fa-exclamation-circle" style="font-size:1rem;"></i>
            <strong>Missed Follow-ups Filter Active</strong>
            &nbsp;— Showing leads with overdue follow-up dates that require attention
        </span>
        <button onclick="clearMissedFilter()" title="Clear filter" style="
            background:none; border:1px solid #fca5a5; color:#dc2626; cursor:pointer;
            font-size:0.8rem; padding:4px 10px; border-radius:6px;
            display:flex; align-items:center; gap:5px; transition:background 0.15s;
        " onmouseover="this.style.background='#fee2e2'" onmouseout="this.style.background='none'">
            <i class="fas fa-times"></i> Clear Filter
        </button>
    `;

    const targets = [
        document.querySelector('.leads-table-container'),
        document.querySelector('.table-container'),
        document.querySelector('.table-wrap'),
        document.querySelector('.leads-content'),
        document.querySelector('table')
    ];
    let inserted = false;
    for (const target of targets) {
        if (target) {
            target.parentNode.insertBefore(banner, target);
            inserted = true;
            break;
        }
    }
    if (!inserted) {
        const main = document.querySelector('main') || document.querySelector('.main-content') || document.body;
        main.prepend(banner);
    }
}

// Clear missed filter and reload
function clearMissedFilter() {
    const banner = document.getElementById('missed-filter-banner');
    if (banner) banner.remove();
    currentFilters.missedFollowups = false;
    history.replaceState(null, '', '/leads');
    loadLeads();
}

// Set current date
function setCurrentDate() {
    const now = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const el = document.getElementById('current-date');
    if (el) el.textContent = now.toLocaleDateString('en-US', options);
}

// Setup event listeners
function setupEventListeners() {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') searchLeads();
        });
    }
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeAllModals();
    });
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function (e) {
            if (e.target === this) closeModal(this.id);
        });
    });
    const actionMenu = document.getElementById('action-menu');
    if (actionMenu) {
        actionMenu.addEventListener('click', function (e) {
            if (e.target === this) closeActionMenu();
        });
    }
}

// Load leads from API
async function loadLeads() {
    try {
        showLoading(true);

        const params = new URLSearchParams({ page: currentPage, limit: pageSize });

        // ===== KEY FIX: if missedFollowups, ONLY send filter=missed, nothing else =====
        if (currentFilters.missedFollowups) {
            params.append('filter', 'missed');
        } else {
            // Only append other filters when NOT in missed mode
            if (currentFilters.status) params.append('status', currentFilters.status);
            if (currentFilters.owner) params.append('owner', currentFilters.owner);
            if (currentFilters.search) params.append('search', currentFilters.search);
        }

        console.log('Loading leads with params:', params.toString()); // Debug log

        const response = await fetch(`/api/leads?${params.toString()}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        if (data.success) {
            renderLeadsTable(data.data);
            updatePagination(data.pagination);
            updateStats(data.data);
        } else {
            throw new Error(data.detail || 'Failed to load leads');
        }
    } catch (error) {
        console.error('Error loading leads:', error);
        showNotification('Failed to load leads', 'error');
        renderEmptyTable('Failed to load leads. Please try again.');
    } finally {
        showLoading(false);
    }
}

// Render leads table
function renderLeadsTable(leads) {
    const tbody = document.getElementById('leads-table-body');

    if (!leads || leads.length === 0) {
        renderEmptyTable(currentFilters.missedFollowups ? 'No missed follow-up leads found' : 'No leads found');
        return;
    }

    tbody.innerHTML = leads.map(lead => `
        <tr data-lead-id="${lead.lead_id}">
            <td><strong>${escapeHtml(lead.lead_id)}</strong></td>

            <td>
                <div class="company-info">
                    <strong>${escapeHtml(lead.company_name)}</strong>
                    ${lead.industry_type ? `<br><small>${escapeHtml(lead.industry_type)}</small>` : ''}
                </div>
            </td>

            <td>
                <div class="contact-info">
                    <strong>${escapeHtml(lead.customer_name)}</strong>
                    ${lead.designation_customer ? `<br><small>${escapeHtml(lead.designation_customer)}</small>` : ''}
                </div>
            </td>

            <td><a href="mailto:${escapeHtml(lead.email_id)}">${escapeHtml(lead.email_id)}</a></td>

            <td><a href="tel:${escapeHtml(lead.contact_no)}">${escapeHtml(formatPhoneNumber(lead.contact_no))}</a></td>

            <td>
                <span class="status-badge status-${getStatusClass(lead.lead_status)}">
                    ${escapeHtml(lead.lead_status || 'New')}
                </span>
            </td>

            <td><span class="source-badge">${escapeHtml(lead.lead_source || 'N/A')}</span></td>

            <td>${formatDate(lead.created_at)}</td>

            <td>${formatDate(lead.updated_at)}</td>

            <!-- ✅ ADD THIS -->
            <td>${formatRemarks(lead.remarks)}</td>

            <td>
                <div class="action-buttons">
                    <button onclick="viewLeadDetail('${lead.lead_id}')">View</button>
                </div>
            </td>
        </tr>
    `).join('');
}

// Render empty table state
function renderEmptyTable(message) {
    const tbody = document.getElementById('leads-table-body');
    tbody.innerHTML = `
        <tr>
            <td colspan="10" class="empty-state">
                <div class="empty-state-content">
                    <i class="fas fa-${currentFilters.missedFollowups ? 'check-circle' : 'inbox'}"></i>
                    <h4>${message}</h4>
                    ${currentFilters.missedFollowups ? `
                        <p>No leads have overdue follow-up dates — great job staying on top of things!</p>
                        <button class="btn btn-primary" onclick="clearMissedFilter()">
                            <i class="fas fa-times"></i> Clear Missed Filter
                        </button>
                    ` : currentFilters.search || currentFilters.status ? `
                        <p>Try changing your filters or search criteria</p>
                        <button class="btn btn-primary" onclick="clearFilters()">Clear Filters</button>
                    ` : currentUserPermissions.can_create_leads ? `
                        <p>Get started by adding your first lead</p>
                        <a href="/add-lead" class="btn btn-primary"><i class="fas fa-plus"></i> Add First Lead</a>
                    ` : `<p>No leads have been added yet</p>`}
                </div>
            </td>
        </tr>
    `;
}

// Update pagination controls
function updatePagination(pagination) {
    totalPages = pagination.pages || 1;
    const showingFrom = ((currentPage - 1) * pageSize) + 1;
    const showingTo = Math.min(currentPage * pageSize, pagination.total);

    ['showing-from', 'showing-to', 'total-leads'].forEach((id, i) => {
        const el = document.getElementById(id);
        if (el) el.textContent = [showingFrom, showingTo, pagination.total][i];
    });

    ['first-page', 'prev-page'].forEach(id => { const el = document.getElementById(id); if (el) el.disabled = currentPage === 1; });
    ['next-page', 'last-page'].forEach(id => { const el = document.getElementById(id); if (el) el.disabled = currentPage === totalPages; });

    const pageNumbersContainer = document.getElementById('page-numbers');
    if (pageNumbersContainer) {
        pageNumbersContainer.innerHTML = '';
        let startPage = Math.max(1, currentPage - 2);
        let endPage = Math.min(totalPages, currentPage + 2);
        if (currentPage <= 3) endPage = Math.min(5, totalPages);
        if (currentPage >= totalPages - 2) startPage = Math.max(1, totalPages - 4);
        for (let i = startPage; i <= endPage; i++) {
            const pageBtn = document.createElement('button');
            pageBtn.className = `page-number ${i === currentPage ? 'active' : ''}`;
            pageBtn.textContent = i;
            pageBtn.onclick = () => goToPage(i);
            pageNumbersContainer.appendChild(pageBtn);
        }
    }
}

// Update stats summary
function updateStats(leads) {
    const ids = ['total-leads-count', 'new-leads-count', 'contacted-leads-count', 'converted-leads-count'];
    if (!leads || leads.length === 0) {
        ids.forEach(id => { const el = document.getElementById(id); if (el) el.textContent = '0'; });
        return;
    }
    let total = leads.length, newCount = 0, contactedCount = 0, convertedCount = 0;
    leads.forEach(lead => {
        switch (lead.lead_status) {
            case 'New': newCount++; break;
            case 'Contacted': case 'Proposal Sent': case 'Negotiation': contactedCount++; break;
            case 'Converted': convertedCount++; break;
        }
    });
    const vals = [total, newCount, contactedCount, convertedCount];
    ids.forEach((id, i) => { const el = document.getElementById(id); if (el) el.textContent = vals[i]; });
}

function goToPage(page) {
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    loadLeads();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function changePageSize() {
    pageSize = parseInt(document.getElementById('page-size').value);
    currentPage = 1;
    loadLeads();
}

function applyFilters() {
    const banner = document.getElementById('missed-filter-banner');
    if (banner) banner.remove();
    history.replaceState(null, '', '/leads');

    currentFilters = {
        status: document.getElementById('status-filter').value,
        source: document.getElementById('source-filter').value,
        owner: document.getElementById('owner-filter') ? document.getElementById('owner-filter').value : '',
        dateFrom: document.getElementById('date-from').value,
        dateTo: document.getElementById('date-to').value,
        search: document.getElementById('search-input').value.trim(),
        missedFollowups: false
    };
    currentPage = 1;
    loadLeads();
    showNotification('Filters applied', 'success');
}

function searchLeads() {
    const searchTerm = document.getElementById('search-input').value.trim();
    currentFilters.search = searchTerm;
    currentFilters.missedFollowups = false;
    const banner = document.getElementById('missed-filter-banner');
    if (banner) banner.remove();
    currentPage = 1;
    loadLeads();
}

function clearFilters() {
    ['status-filter', 'source-filter', 'owner-filter', 'search-input'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    const today = new Date().toISOString().split('T')[0];
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    document.getElementById('date-from').value = thirtyDaysAgo.toISOString().split('T')[0];
    document.getElementById('date-to').value = today;

    const banner = document.getElementById('missed-filter-banner');
    if (banner) banner.remove();
    history.replaceState(null, '', '/leads');

    currentFilters = {
        status: '', source: '', owner: '',
        dateFrom: document.getElementById('date-from').value,
        dateTo: document.getElementById('date-to').value,
        search: '', missedFollowups: false
    };
    currentPage = 1;
    loadLeads();
    showNotification('Filters cleared', 'success');
}

async function exportLeads() {
    try {
        showNotification('Preparing export...', 'info');
        setTimeout(() => { showNotification('Export feature will be available soon', 'info'); }, 1000);
    } catch (error) {
        showNotification('Failed to export leads', 'error');
    }
}

function viewLeadDetail(leadId) { window.location.href = `/lead-detail/${leadId}`; }
function editLeadDetail(leadId) { window.location.href = `/edit-lead/${leadId}`; }

function openActionMenu(event, leadId, leadData) {
    event.stopPropagation();
    selectedLeadId = leadId;
    currentLeadData = leadData ? JSON.parse(leadData) : null;
    const menu = document.getElementById('action-menu');
    const button = event.target.closest('button');
    const rect = button.getBoundingClientRect();
    menu.style.display = 'flex';
    let top = rect.bottom + 5, left = rect.left;
    if (top + 300 > window.innerHeight) top = rect.top - 300;
    if (left + 300 > window.innerWidth) left = window.innerWidth - 320;
    menu.querySelector('.action-menu-content').style.top = `${top}px`;
    menu.querySelector('.action-menu-content').style.left = `${left}px`;
}

function closeActionMenu() {
    const menu = document.getElementById('action-menu');
    if (menu) menu.style.display = 'none';
    selectedLeadId = null;
    currentLeadData = null;
}

function viewLead() { if (selectedLeadId) viewLeadDetail(selectedLeadId); closeActionMenu(); }
function editLead() { if (selectedLeadId) editLeadDetail(selectedLeadId); closeActionMenu(); }

function deleteLead() {
    if (!selectedLeadId) return;
    if (!currentUserPermissions.can_delete_leads) {
        showNotification('You do not have permission to delete leads', 'error');
        closeActionMenu();
        return;
    }
    closeActionMenu();
    openModal('delete-modal');
}

async function confirmDeleteLead() {
    try {
        showLoading(true);
        const response = await fetch(`/api/leads/${selectedLeadId}`, {
            method: 'DELETE', headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        if (data.success) {
            showNotification('Lead deleted successfully', 'success');
            closeModal('delete-modal');
            loadLeads();
        } else {
            throw new Error(data.detail || 'Failed to delete lead');
        }
    } catch (error) {
        showNotification('Failed to delete lead: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

function addActivity() { showNotification('Add activity feature will be available soon', 'info'); closeActionMenu(); }

function changeStatus() {
    if (!selectedLeadId || !currentLeadData) return;
    document.getElementById('new-status').value = currentLeadData.lead_status || 'New';
    document.getElementById('status-remarks').value = '';
    openModal('status-modal');
    closeActionMenu();
}

async function updateLeadStatus() {
    try {
        const newStatus = document.getElementById('new-status').value;
        const remarks = document.getElementById('status-remarks').value.trim();
        if (!selectedLeadId) return;
        showLoading(true);
        const response = await fetch(`/api/leads/${selectedLeadId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lead_status: newStatus, remarks: remarks || null })
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        if (data.success) {
            showNotification('Lead status updated successfully', 'success');
            closeModal('status-modal');
            loadLeads();
        } else {
            throw new Error(data.detail || 'Failed to update lead status');
        }
    } catch (error) {
        showNotification('Failed to update status: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

function openModal(modalId) { document.getElementById(modalId).style.display = 'flex'; document.body.style.overflow = 'hidden'; }
function closeModal(modalId) { document.getElementById(modalId).style.display = 'none'; document.body.style.overflow = 'auto'; }
function closeAllModals() {
    document.querySelectorAll('.modal').forEach(modal => { modal.style.display = 'none'; });
    closeActionMenu();
    document.body.style.overflow = 'auto';
}

function showLoading(isLoading) {
    const loadingOverlay = document.getElementById('loading-overlay') || createLoadingOverlay();
    loadingOverlay.style.display = isLoading ? 'flex' : 'none';
}

function createLoadingOverlay() {
    const overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `<div class="loading-spinner-large"><i class="fas fa-spinner fa-spin"></i><p>Loading...</p></div>`;
    overlay.style.display = 'none';
    document.body.appendChild(overlay);
    return overlay;
}

function showNotification(message, type = 'info') {
    const existing = document.querySelector('.notification-toast');
    if (existing) existing.remove();
    const notification = document.createElement('div');
    notification.className = `notification-toast notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${getNotificationIcon(type)}"></i>
            <span>${escapeHtml(message)}</span>
        </div>
        <button class="notification-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    document.body.appendChild(notification);
    setTimeout(() => { notification.classList.add('show'); }, 10);
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.remove('show');
            setTimeout(() => { if (notification.parentNode) notification.remove(); }, 300);
        }
    }, 5000);
}

function getNotificationIcon(type) {
    return { success: 'check-circle', error: 'exclamation-circle', warning: 'exclamation-triangle', info: 'info-circle' }[type] || 'info-circle';
}

function getStatusClass(status) {
    if (!status) return 'new';
    const statusMap = {
        'New': 'new', 'new': 'new', 'Contacted': 'contacted', 'contacted': 'contacted',
        'Proposal Sent': 'proposal', 'Proposal': 'proposal', 'Negotiation': 'negotiation',
        'negotiation': 'negotiation', 'Converted': 'converted', 'converted': 'converted',
        'Closed': 'converted', 'Lost': 'lost', 'lost': 'lost'
    };
    return statusMap[status] || 'new';
}

function formatPhoneNumber(phone) {
    if (!phone) return 'N/A';
    const cleaned = phone.toString().replace(/\D/g, '');
    if (cleaned.length === 10) return cleaned.replace(/(\d{3})(\d{3})(\d{4})/, '($1) $2-$3');
    if (cleaned.length > 10) return `+${cleaned.slice(0, cleaned.length - 10)} (${cleaned.slice(-10, -7)}) ${cleaned.slice(-7, -4)}-${cleaned.slice(-4)}`;
    return phone;
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return 'Invalid date';
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch (e) { return 'N/A'; }
}

function escapeHtml(text) {
    if (!text) return '';
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return text.toString().replace(/[&<>"']/g, m => map[m]);
}

function formatRemarks(remarks) {
    if (!remarks) return "";

    try {
        const attempts = JSON.parse(remarks);

        return attempts.map(a => {
            const date = new Date(a.date).toLocaleDateString('en-GB', {
                day: 'numeric',
                month: 'short'
            });

            return `<b>${a.type}</b>: ${date}`;
        }).join('<br>');

    } catch {
        return remarks;
    }
}

function toggleSidebar() { document.querySelector('.sidebar').classList.toggle('active'); }

async function logout() {
    try {
        if (window.PermissionManager) window.PermissionManager.clear();
        const response = await fetch('/api/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        const data = await response.json();
        if (data.success) window.location.href = '/login';
        else throw new Error(data.detail || 'Logout failed');
    } catch (error) {
        showNotification('Logout failed. Please try again.', 'error');
    }
}

async function loadStats() {
    try { showLoading(true); await loadLeads(); showNotification('Stats updated', 'success'); }
    catch (e) { showNotification('Failed to update stats', 'error'); }
    finally { showLoading(false); }
}

async function loadConversionChart() { showNotification('Conversion chart data is not yet available', 'info'); }
function exportChart() { showNotification('Export feature is not yet implemented', 'info'); }
function refreshCharts() { loadLeads(); }
function generateReport() { showNotification('Report generation is not yet implemented', 'info'); }
function openCalendar() { showNotification('Calendar feature is not yet implemented', 'info'); }

// Inject styles
const leadsStyles = document.createElement('style');
leadsStyles.textContent = `
.empty-state { text-align:center; padding:60px 20px !important; }
.empty-state-content { max-width:400px; margin:0 auto; }
.empty-state-content i { font-size:3rem; color:#e0e6ff; margin-bottom:20px; }
.empty-state-content h4 { color:#666; margin-bottom:10px; font-size:1.2rem; }
.empty-state-content p { color:#999; margin-bottom:20px; font-size:0.95rem; }
.empty-state-content .btn { padding:12px 24px; font-size:1rem; }
.source-badge { display:inline-block; padding:4px 10px; background:#f0f7ff; color:#667eea; border-radius:12px; font-size:0.8rem; font-weight:500; }
.email-link { color:#667eea; text-decoration:none; } .email-link:hover { color:#4a5fc1; text-decoration:underline; }
.phone-link { color:#495057; text-decoration:none; } .phone-link:hover { color:#667eea; }
.company-info small, .contact-info small { color:#888; font-size:0.8rem; }
.company-info, .contact-info { line-height:1.4; }
.loading-overlay { position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(255,255,255,0.9); display:flex; align-items:center; justify-content:center; z-index:9999; }
.loading-spinner-large { text-align:center; padding:30px; background:white; border-radius:15px; box-shadow:0 10px 30px rgba(0,0,0,0.1); }
.loading-spinner-large i { font-size:3rem; color:#667eea; margin-bottom:15px; }
.loading-spinner-large p { color:#666; font-size:1rem; margin:0; }
.notification-toast { position:fixed; top:20px; right:20px; background:white; border-radius:10px; padding:15px 20px; box-shadow:0 5px 20px rgba(0,0,0,0.15); display:flex; align-items:center; gap:15px; min-width:300px; max-width:400px; transform:translateX(400px); transition:transform 0.3s ease; z-index:10000; }
.notification-toast.show { transform:translateX(0); }
.notification-content { display:flex; align-items:center; gap:10px; flex:1; }
.notification-success { border-left:4px solid #4CAF50; } .notification-error { border-left:4px solid #f44336; }
.notification-warning { border-left:4px solid #FF9800; } .notification-info { border-left:4px solid #2196F3; }
.notification-content i { font-size:1.2rem; }
.notification-success .notification-content i { color:#4CAF50; } .notification-error .notification-content i { color:#f44336; }
.notification-warning .notification-content i { color:#FF9800; } .notification-info .notification-content i { color:#2196F3; }
.notification-close { background:none; border:none; color:#999; cursor:pointer; padding:5px; font-size:0.9rem; }
.notification-close:hover { color:#666; }
`;
document.head.appendChild(leadsStyles);

// Current user permissions (from template)
const currentUserPermissions = {
    can_view_leads: {{ user.permissions.can_view_leads| lower }},
can_create_leads: { { user.permissions.can_create_leads | lower } },
can_edit_leads: { { user.permissions.can_edit_leads | lower } },
can_delete_leads: { { user.permissions.can_delete_leads | lower } },
can_view_users: { { user.permissions.can_view_users | lower } },
can_manage_users: { { user.permissions.can_manage_users | lower } },
can_view_reports: { { user.permissions.can_view_reports | lower } },
can_export_data: { { user.permissions.can_export_data | lower } }
};
