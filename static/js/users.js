// ============================================================
// users.js - Fixed Version
// Fixes:
// 1. updateUser - removed wrong Authorization header, uses credentials:'include'
// 2. deleteUser - same fix
// 3. showAddUserModal - fixed wrong element ID ('role' → 'new_role')
// 4. updatePermissionsByRole - renamed to match HTML onchange call
// 5. API response - data.users (not data.data)
// ============================================================

alert("JS FILE LOADED");

let currentUser = null;
let allUsers = [];
let filteredUsers = [];
let allDesignations = [];

document.addEventListener('DOMContentLoaded', async function () {
    currentUser = JSON.parse(localStorage.getItem('user'));

    if (!currentUser) {
        window.location.href = '/';
        return;
    }

    if (!currentUser.hasOwnProperty('is_admin')) {
        currentUser.is_admin = currentUser.role === 'admin';
    }

    await loadUsersData();
    await loadDesignations();
    initializeEventListeners();
    initializeSearch();
});

// ─── Refresh button ──────────────────────────────────────────
function loadUsers() {
    loadUsersData();
}

// ─── Load users from API ─────────────────────────────────────
async function loadUsersData() {
    try {
        showLoading(true);
        const tbody = document.getElementById('usersTableBody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="14" style="text-align:center;padding:40px;color:#6b7280;"><i class="fas fa-spinner fa-spin" style="font-size:2rem;"></i><p>Loading users...</p></td></tr>';
        }

        const response = await fetch('/api/users', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'   // ✅ cookie auth
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        if (data.success) {
            // ✅ API returns { success, users: [] }
            allUsers = data.users || data.data || [];
            filteredUsers = [...allUsers];
            updateUsersTable();
            updateUserStats();
        } else {
            throw new Error(data.detail || 'Failed to load users');
        }
    } catch (error) {
        console.error('Error loading users:', error);
        showError('Failed to load users: ' + error.message);
        document.getElementById('usersTableBody').innerHTML = `
            <tr><td colspan="14" style="text-align:center;padding:40px;color:#6b7280;">
                <i class="fas fa-exclamation-circle" style="font-size:2rem;color:#dc3545;"></i>
                <p>Failed to load users. <button class="btn primary" onclick="loadUsersData()">Retry</button></p>
            </td></tr>`;
    } finally {
        showLoading(false);
    }
}

// ─── Render table ─────────────────────────────────────────────
function updateUsersTable() {
    const tbody = document.getElementById('usersTableBody');
    if (!filteredUsers.length) {
        tbody.innerHTML = `<tr><td colspan="14" style="text-align:center;padding:40px;color:#6b7280;">
            <i class="fas fa-users" style="font-size:3rem;margin-bottom:10px;display:block;color:#dee2e6;"></i>
            <h4>No users found</h4><p>Try adjusting filters or add a new user.</p>
            <button class="btn primary" onclick="showAddUserModal()"><i class="fas fa-user-plus"></i> Add User</button>
        </td></tr>`;
        return;
    }

    let html = '';
    filteredUsers.forEach((user, index) => {
        const isActive = user.is_active === 1 || user.is_active === true;
        html += `
        <tr>
            <td>${index + 1}</td>
            <td>${renderUserPhoto(user)}</td>
            <td>${escapeHtml(user.username || '')}</td>
            <td>${escapeHtml(user.full_name || '')}</td>
            <td>${escapeHtml(user.email || '')}</td>
            <td>${escapeHtml(user.designation || '-')}</td>
            <td>${escapeHtml(user.mobile_no || '-')}</td>
            <td>${user.date_of_birth ? formatDate(user.date_of_birth) : '-'}</td>
            <td><span class="password-masked">••••••••</span></td>
            <td><span class="role-badge ${user.role}">${formatRoleName(user.role)}</span></td>
            <td><span class="status-badge ${isActive ? 'active' : 'inactive'}">${isActive ? 'Active' : 'Inactive'}</span></td>
            <td>${escapeHtml(user.created_by_name || 'System')}</td>
            <td>${formatDate(user.created_at)}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn-icon" title="View" onclick="viewUser(${user.id})"><i class="fas fa-eye"></i></button>
                    ${user.id !== currentUser.user_id
                ? `<button class="btn-icon" title="Edit" onclick="editUser(${user.id})"><i class="fas fa-edit"></i></button>`
                : ''}
                    ${(currentUser.is_admin || currentUser.permissions?.can_manage_users) && user.id !== currentUser.user_id
                ? `<button class="btn-icon danger" title="Deactivate" onclick="deleteUser(${user.id})"><i class="fas fa-trash"></i></button>`
                : ''}
                    ${(currentUser.is_admin || currentUser.permissions?.can_manage_users) && !isActive && user.id !== currentUser.user_id
                ? `<button class="btn-icon success" title="Activate" onclick="activateUser(${user.id})"><i class="fas fa-check-circle"></i></button>`
                : ''}
                </div>
            </td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

// ─── Stats ────────────────────────────────────────────────────
function updateUserStats() {
    const active = allUsers.filter(u => u.is_active === 1 || u.is_active === true).length;
    const inactive = allUsers.length - active;
    const el = id => document.getElementById(id);
    if (el('users-count')) el('users-count').textContent = allUsers.length;
    if (el('active-count')) el('active-count').textContent = active;
    if (el('inactive-count')) el('inactive-count').textContent = inactive;
}

// ─── Search & Filter ──────────────────────────────────────────
function initializeSearch() {
    const input = document.getElementById('searchInput');
    if (!input) return;
    let t;
    input.addEventListener('input', () => { clearTimeout(t); t = setTimeout(filterUsers, 400); });
}

function filterUsers() {
    const role = document.getElementById('roleFilter')?.value || '';
    const status = document.getElementById('statusFilter')?.value || '';
    const query = (document.getElementById('searchInput')?.value || '').toLowerCase();

    filteredUsers = allUsers.filter(u => {
        if (role && u.role !== role) return false;
        if (status) {
            const active = u.is_active === 1 || u.is_active === true;
            if (status === 'active' && !active) return false;
            if (status === 'inactive' && active) return false;
        }
        if (query) {
            const text = `${u.username} ${u.full_name} ${u.email} ${u.role}`.toLowerCase();
            if (!text.includes(query)) return false;
        }
        return true;
    });
    updateUsersTable();
}

// ─── Event listeners ─────────────────────────────────────────
function initializeEventListeners() {
    document.getElementById('roleFilter')?.addEventListener('change', filterUsers);
    document.getElementById('statusFilter')?.addEventListener('change', filterUsers);

    document.getElementById('addUserForm')?.addEventListener('submit', handleAddUserSubmit);
    document.getElementById('addDesignationForm')?.addEventListener('submit', handleAddDesignationSubmit);

    // ✅ Edit form submit
    document.getElementById('editUserForm')?.addEventListener('submit', function (e) {
        e.preventDefault();
        const userId = document.getElementById('edit_user_id').value;
        updateUser(userId);
    });

    // Auto-fill full name
    document.getElementById('new_first_name')?.addEventListener('input', updateFullNameFromParts);
    document.getElementById('new_last_name')?.addEventListener('input', updateFullNameFromParts);
}

// ─── Add User Modal ───────────────────────────────────────────
function showAddUserModal() {
    const isAdmin = currentUser?.is_admin === true;
    const hasPerm = currentUser?.permissions?.can_manage_users === true;
    if (!isAdmin && !hasPerm) { showError('You do not have permission to manage users'); return; }

    document.getElementById('addUserForm')?.reset();
    // ✅ Fixed: correct element ID
    const roleEl = document.getElementById('new_role');
    if (roleEl) roleEl.value = '';
    resetPermissionCheckboxes();
    document.getElementById('addUserModal').style.display = 'flex';
}

function closeAddUserModal() { closeModal('addUserModal'); }

function resetPermissionCheckboxes() {
    ['perm_view_leads', 'perm_create_leads', 'perm_edit_leads', 'perm_view_reports', 'perm_export_data'].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.checked = true; el.disabled = false; }
    });
    ['perm_delete_leads', 'perm_view_users', 'perm_manage_users'].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.checked = false; el.disabled = false; }
    });
}

// ✅ Fixed: function name matches HTML onchange="updatePermissionsByRole()"
function updatePermissionsByRole() {
    const role = document.getElementById('new_role')?.value;
    const map = {
        admin: { perm_view_leads: true, perm_create_leads: true, perm_edit_leads: true, perm_delete_leads: true, perm_view_users: true, perm_manage_users: true, perm_view_reports: true, perm_export_data: true },
        manager: { perm_view_leads: true, perm_create_leads: true, perm_edit_leads: true, perm_delete_leads: false, perm_view_users: true, perm_manage_users: false, perm_view_reports: true, perm_export_data: true },
        sales: { perm_view_leads: true, perm_create_leads: true, perm_edit_leads: true, perm_delete_leads: false, perm_view_users: false, perm_manage_users: false, perm_view_reports: true, perm_export_data: true },
        viewer: { perm_view_leads: true, perm_create_leads: false, perm_edit_leads: false, perm_delete_leads: false, perm_view_users: false, perm_manage_users: false, perm_view_reports: true, perm_export_data: false }
    };
    if (!role || !map[role]) { resetPermissionCheckboxes(); return; }
    Object.entries(map[role]).forEach(([id, val]) => {
        const el = document.getElementById(id);
        if (el) { el.checked = val; el.disabled = (role === 'viewer'); }
    });
}

// ─── Create User ──────────────────────────────────────────────
async function handleAddUserSubmit(e) {
    e.preventDefault();
    const btn = e.submitter || e.target.querySelector('button[type="submit"]');
    const orig = btn?.innerHTML;
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...'; }

    try {
        // Upload photo if provided
        let photoPath = null;
        const photoInput = document.getElementById('new_photo');
        if (photoInput?.files?.[0]) {
            const fd = new FormData();
            fd.append('file', photoInput.files[0]);
            const up = await fetch('/api/upload/photo', { method: 'POST', body: fd, credentials: 'include' });
            const upData = await up.json();
            if (up.ok && upData.success) photoPath = upData.path;
            else throw new Error(upData.detail || 'Photo upload failed');
        }

        const userData = {
            username: document.getElementById('new_username')?.value?.trim() || '',
            password: document.getElementById('new_password')?.value || '',
            first_name: document.getElementById('new_first_name')?.value?.trim() || '',
            last_name: document.getElementById('new_last_name')?.value?.trim() || '',
            full_name: document.getElementById('new_full_name')?.value?.trim() || '',
            email: document.getElementById('new_email')?.value?.trim() || '',
            designation: document.getElementById('new_designation')?.value || null,
            mobile_no: document.getElementById('new_mobile_no')?.value || null,
            date_of_birth: document.getElementById('new_date_of_birth')?.value || null,
            photo: photoPath,
            role: document.getElementById('new_role')?.value || '',
            permissions: {
                can_view_leads: document.getElementById('perm_view_leads')?.checked || false,
                can_create_leads: document.getElementById('perm_create_leads')?.checked || false,
                can_edit_leads: document.getElementById('perm_edit_leads')?.checked || false,
                can_delete_leads: document.getElementById('perm_delete_leads')?.checked || false,
                can_view_users: document.getElementById('perm_view_users')?.checked || false,
                can_manage_users: document.getElementById('perm_manage_users')?.checked || false,
                can_view_reports: document.getElementById('perm_view_reports')?.checked || false,
                can_export_data: document.getElementById('perm_export_data')?.checked || false,
            }
        };

        if (!userData.username) throw new Error('Username is required');
        if (!userData.password) throw new Error('Password is required');
        if (!userData.full_name) throw new Error('Full name is required');
        if (!userData.email) throw new Error('Email is required');
        if (!userData.role) throw new Error('Role is required');

        const res = await fetch('/api/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',   // ✅ cookie auth
            body: JSON.stringify(userData)
        });
        const data = await res.json();

        if (data.success) {
            showSuccess('User created successfully!');
            closeAddUserModal();
            await loadUsersData();
        } else {
            throw new Error(data.detail || 'Failed to create user');
        }
    } catch (err) {
        console.error('Create user error:', err);
        showError(err.message || 'Failed to create user');
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = orig || 'Create User'; }
    }
}

// ─── View User ────────────────────────────────────────────────
function viewUser(userId) {
    const user = allUsers.find(u => u.id == userId);
    if (!user) { showError('User not found'); return; }

    let perms = {};
    try { perms = JSON.parse(user.permissions || '{}'); } catch { }

    const isActive = user.is_active === 1 || user.is_active === true;
    const html = `
        <div style="display:flex;align-items:center;gap:20px;margin-bottom:20px;padding-bottom:15px;border-bottom:1px solid #dee2e6;">
            <div>${renderUserPhoto(user)}</div>
            <div>
                <h3 style="margin:0;">${escapeHtml(user.full_name || '')}</h3>
                <p style="margin:4px 0;color:#6b7280;">@${escapeHtml(user.username)} · ${escapeHtml(user.email)}</p>
                <div style="display:flex;gap:8px;margin-top:8px;">
                    <span class="role-badge ${user.role}">${formatRoleName(user.role)}</span>
                    <span class="status-badge ${isActive ? 'active' : 'inactive'}">${isActive ? 'Active' : 'Inactive'}</span>
                </div>
            </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:20px;">
            <div><strong>Designation:</strong> ${escapeHtml(user.designation || '-')}</div>
            <div><strong>Mobile:</strong> ${escapeHtml(user.mobile_no || '-')}</div>
            <div><strong>DOB:</strong> ${user.date_of_birth ? formatDate(user.date_of_birth) : '-'}</div>
            <div><strong>Created By:</strong> ${escapeHtml(user.created_by_name || 'System')}</div>
            <div><strong>Created At:</strong> ${formatDate(user.created_at)}</div>
        </div>
        <div>
            <strong>Permissions:</strong>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;">
                ${Object.entries(perms).map(([k, v]) => `
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="width:22px;height:22px;border-radius:50%;background:${v ? '#c6f6d5' : '#fed7d7'};
                            color:${v ? '#22543d' : '#742a2a'};display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;">
                            ${v ? '✓' : '✗'}
                        </span>
                        <span>${formatPermissionName(k)}</span>
                    </div>`).join('')}
            </div>
        </div>
        <div style="margin-top:20px;display:flex;gap:10px;justify-content:flex-end;">
            <button class="btn ghost" onclick="closeModal('viewUserModal')">Close</button>
            ${user.id !== currentUser.user_id
            ? `<button class="btn primary" onclick="closeModal('viewUserModal');editUser(${user.id})"><i class="fas fa-edit"></i> Edit</button>`
            : ''}
        </div>`;

    document.getElementById('viewUserContent').innerHTML = html;
    document.getElementById('viewUserModal').style.display = 'flex';
}

// ─── Edit User ────────────────────────────────────────────────
async function editUser(userId) {
    const user = allUsers.find(u => u.id == userId);
    if (!user) { showError('User not found'); return; }
    if (user.id === currentUser.user_id) { showError('Cannot edit your own account from here'); return; }

    document.getElementById('edit_user_id').value = user.id;
    document.getElementById('edit_username').value = user.username || '';
    document.getElementById('edit_password').value = '';
    document.getElementById('edit_first_name').value = user.first_name || '';
    document.getElementById('edit_last_name').value = user.last_name || '';
    document.getElementById('edit_full_name').value = user.full_name || '';
    document.getElementById('edit_email').value = user.email || '';
    document.getElementById('edit_mobile_no').value = user.mobile_no || '';
    document.getElementById('edit_date_of_birth').value = user.date_of_birth || '';
    document.getElementById('edit_role').value = user.role || '';

    // Populate designation dropdown then set value
    await loadDesignations();
    document.getElementById('edit_designation').value = user.designation || '';

    closeModal('viewUserModal');
    document.getElementById('editUserModal').style.display = 'flex';
}

// ─── ✅ Update User (MAIN FIX) ────────────────────────────────
async function updateUser(userId) {
    console.log("🔥 updateUser called with ID:", userId);

    const form = document.getElementById('editUserForm');

    // ✅ Form validation
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn.innerHTML;

    // ✅ Button loading state
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';

    try {
        // ✅ Collect data safely
        const updateData = {
            first_name: document.getElementById('edit_first_name')?.value?.trim() || null,
            last_name: document.getElementById('edit_last_name')?.value?.trim() || null,
            full_name: document.getElementById('edit_full_name')?.value?.trim(),
            email: document.getElementById('edit_email')?.value?.trim(),
            designation: document.getElementById('edit_designation')?.value || null,
            mobile_no: document.getElementById('edit_mobile_no')?.value || null,
            date_of_birth: document.getElementById('edit_date_of_birth')?.value || null,
            role: document.getElementById('edit_role')?.value
        };

        // ✅ Password optional
        const pwd = document.getElementById('edit_password')?.value;
        if (pwd && pwd.trim()) {
            updateData.password = pwd.trim();
        }

        console.log("📤 Sending data:", updateData);

        // ✅ API call
        const res = await fetch(`/api/users/${userId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify(updateData)
        });

        const data = await res.json();
        console.log("📥 Response:", data);

        // ❌ Handle error
        if (!res.ok) {
            throw new Error(data.detail || `HTTP ${res.status}`);
        }

        // ✅ Success
        if (data.success) {
            showSuccess("User updated successfully!");
            closeEditUserModal();

            // refresh table
            if (typeof loadUsersData === "function") {
                await loadUsersData();
            }
        } else {
            throw new Error(data.detail || "Update failed");
        }

    } catch (err) {
        console.error("❌ Update error:", err);
        showError("Failed to update user: " + err.message);
    } finally {
        // ✅ Restore button
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// ─── Delete / Activate User ───────────────────────────────────
async function deleteUser(userId) {
    const user = allUsers.find(u => u.id == userId);
    if (!user) return;
    if (user.id === currentUser.user_id) { showError('Cannot deactivate your own account'); return; }
    if (!confirm(`Deactivate "${user.full_name}"?`)) return;

    try {
        showLoading(true);
        // ✅ credentials:'include' - no Authorization header
        const res = await fetch(`/api/users/${userId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
        if (data.success) {
            showSuccess(data.message || 'User deactivated');
            await loadUsersData();
            closeModal('viewUserModal');
            closeModal('editUserModal');
        } else throw new Error(data.detail || 'Failed');
    } catch (err) {
        showError('Failed: ' + err.message);
    } finally { showLoading(false); }
}

async function activateUser(userId) {
    const user = allUsers.find(u => u.id == userId);
    if (!user) return;
    if (!confirm(`Activate "${user.full_name}"?`)) return;

    try {
        showLoading(true);
        const res = await fetch(`/api/users/${userId}/activate`, {
            method: 'PUT',
            credentials: 'include'
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
        if (data.success) { showSuccess('User activated!'); await loadUsersData(); }
        else throw new Error(data.detail || 'Failed');
    } catch (err) {
        showError('Failed: ' + err.message);
    } finally { showLoading(false); }
}

// ─── Designations ─────────────────────────────────────────────
async function loadDesignations() {
    try {
        const res = await fetch('/api/designations', { credentials: 'include' });
        const data = await res.json();
        if (data.success) {
            allDesignations = data.designations || [];
            populateDesignationSelects();
        }
    } catch (e) { console.error('Designations load error:', e); }
}

function populateDesignationSelects() {
    const opts = ['<option value="">Select designation</option>']
        .concat(allDesignations.map(d => `<option value="${d.name}">${d.name}</option>`))
        .join('');
    const newSel = document.getElementById('new_designation');
    const editSel = document.getElementById('edit_designation');
    if (newSel) newSel.innerHTML = opts;
    if (editSel) editSel.innerHTML = opts;
}

function openAddDesignationModal() {
    document.getElementById('addDesignationForm')?.reset();
    document.getElementById('addDesignationModal').style.display = 'flex';
}
function closeAddDesignationModal() { closeModal('addDesignationModal'); }

async function handleAddDesignationSubmit(e) {
    e.preventDefault();
    const btn = e.submitter || e.target.querySelector('button[type="submit"]');
    const orig = btn?.innerHTML;
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...'; }

    try {
        const name = document.getElementById('designation_name')?.value?.trim();
        if (!name) throw new Error('Designation name required');

        const res = await fetch('/api/designations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ name })
        });
        const data = await res.json();
        if (data.success) {
            showSuccess('Designation added!');
            await loadDesignations();
            closeAddDesignationModal();
        } else throw new Error(data.detail || 'Failed');
    } catch (err) {
        showError(err.message || 'Failed');
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = orig || 'Add Designation'; }
    }
}

// ─── Helpers ──────────────────────────────────────────────────
function updateFullNameFromParts() {
    const first = document.getElementById('new_first_name')?.value?.trim() || '';
    const last = document.getElementById('new_last_name')?.value?.trim() || '';
    const fullEl = document.getElementById('new_full_name');
    if (fullEl) fullEl.value = [first, last].filter(Boolean).join(' ');
}

function formatDate(ds) {
    if (!ds) return '-';
    try { return new Date(ds).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' }); }
    catch { return ds; }
}

function formatRoleName(role) {
    return { admin: 'Administrator', manager: 'Manager', sales: 'Sales Executive', viewer: 'Viewer', oops: 'OOPS', finance: 'Finance', scm: 'SCM' }[role] || role;
}

function formatPermissionName(p) {
    return p.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function getInitials(name) {
    return (name || 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function getPhotoUrl(photo) {
    if (!photo) return '';
    let p = String(photo).trim().replace(/\\/g, '/');
    if (p.startsWith('http://') || p.startsWith('https://')) return p;
    if (p.startsWith('/')) return p;
    const idx = p.toLowerCase().indexOf('static/');
    if (idx !== -1) return '/' + p.slice(idx);
    if (p.startsWith('uploads/') || p.startsWith('images/') || p.startsWith('users/')) return `/static/${p}`;
    return `/static/${p}`;
}

function renderUserPhoto(user) {
    const url = getPhotoUrl(user.photo || '');
    const label = escapeHtml(user.full_name || user.username || 'User');
    if (url) return `<a href="${escapeHtml(url)}" target="_blank"><img class="user-photo-thumb" src="${escapeHtml(url)}" alt="${label}" style="width:36px;height:36px;border-radius:50%;object-fit:cover;"></a>`;
    return `<div class="user-photo-fallback" style="width:36px;height:36px;border-radius:50%;background:#0d6efd;color:white;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.85em;">${getInitials(user.full_name || user.username)}</div>`;
}

function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = String(text);
    return d.innerHTML;
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
}
function closeEditUserModal() { closeModal('editUserModal'); }

function showLoading(show) {
    let el = document.getElementById('loading');
    if (!el && show) {
        el = document.createElement('div');
        el.id = 'loading';
        el.style.cssText = 'position:fixed;inset:0;background:rgba(255,255,255,0.85);display:flex;align-items:center;justify-content:center;z-index:9999;';
        el.innerHTML = '<div style="text-align:center;"><div class="spinner" style="width:50px;height:50px;border:5px solid #f3f3f3;border-top:5px solid #0d6efd;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 15px;"></div><p>Loading...</p></div>';
        document.body.appendChild(el);
    }
    if (el) el.style.display = show ? 'flex' : 'none';
}

function showSuccess(msg) {
    showToast(msg, '#38a169');
}
function showError(msg) {
    showToast(msg, '#e53e3e', 5000);
}
function showToast(msg, bg, duration = 3000) {
    const t = document.createElement('div');
    t.style.cssText = `position:fixed;top:20px;right:20px;padding:15px 20px;border-radius:8px;background:${bg};color:white;z-index:9999;box-shadow:0 5px 15px rgba(0,0,0,0.2);display:flex;align-items:center;gap:10px;max-width:350px;animation:slideIn 0.3s ease;`;
    t.innerHTML = `<span style="flex:1;font-size:14px;">${escapeHtml(msg)}</span><button onclick="this.parentElement.remove()" style="background:none;border:none;color:white;font-size:18px;cursor:pointer;padding:0;">×</button>`;
    document.body.appendChild(t);
    setTimeout(() => { if (t.parentNode) t.remove(); }, duration);
}

// Close modals on outside click
window.addEventListener('click', e => {
    document.querySelectorAll('.modal-overlay').forEach(m => {
        if (e.target === m) m.style.display = 'none';
    });
});

document.addEventListener('DOMContentLoaded', function () {

    const form = document.getElementById('editUserForm');

    if (!form) {
        console.error("❌ editUserForm not found");
        return;
    }

    console.log("✅ editUserForm found");

    form.addEventListener('submit', function (e) {
        e.preventDefault();

        const userId = document.getElementById('edit_user_id').value;

        console.log("👉 SUBMIT CLICKED, ID =", userId);

        if (!userId) {
            alert("User ID missing");
            return;
        }

        updateUser(userId);
    });

});

function handleUpdateClick() {
    const userId = document.getElementById('edit_user_id').value;

    console.log("🟢 Button clicked, ID =", userId);

    if (!userId) {
        alert("User ID missing");
        return;
    }

    updateUser(userId);
}

// Styles
const style = document.createElement('style');
style.textContent = `
@keyframes spin { 0%{transform:rotate(0deg)} 100%{transform:rotate(360deg)} }
@keyframes slideIn { from{transform:translateX(100%);opacity:0} to{transform:translateX(0);opacity:1} }
.role-badge { padding:4px 10px;border-radius:12px;font-size:0.8em;font-weight:600;color:white; }
.role-badge.admin { background:#5b6ef5; }
.role-badge.manager { background:#00b3a4; }
.role-badge.sales { background:#ff9f43; }
.role-badge.viewer { background:#6c757d; }
.role-badge.oops, .role-badge.finance, .role-badge.scm { background:#dc3545; }
.status-badge { padding:4px 10px;border-radius:12px;font-size:0.8em;font-weight:600; }
.status-badge.active { background:#c6f6d5;color:#22543d; }
.status-badge.inactive { background:#fed7d7;color:#742a2a; }
.btn-icon { width:34px;height:34px;border:none;border-radius:6px;background:#f1f5f9;color:#495057;cursor:pointer;display:inline-flex;align-items:center;justify-content:center; }
.btn-icon:hover { background:#0d6efd;color:white; }
.btn-icon.danger:hover { background:#dc3545;color:white; }
.btn-icon.success:hover { background:#198754;color:white; }
.password-masked { color:#6c757d;letter-spacing:2px; }
`;
document.head.appendChild(style);