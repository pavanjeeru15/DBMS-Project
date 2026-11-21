const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const API = (window.CIVICTRACK_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const DEPTS = [
 ['Roads','🛣️','Road repairs, potholes, footpaths and traffic signs.',1],
 ['Water Supply','💧','Water leakage, supply interruptions and quality.',2],
 ['Sanitation','🧹','Waste collection, public cleanliness and litter.',3],
 ['Street Lighting','💡','Non-working streetlights and dark public areas.',4],
 ['Drainage','🌧️','Blocked drains, flooding and sewage concerns.',5],
 ['Electricity','⚡','Public electrical faults and damaged utility equipment.',6]
];
const CATEGORIES = [
 ['Potholes',1,'Roads'],['Road Damage',2,'Roads'],['Garbage',3,'Sanitation'],
 ['Water Supply',4,'Water Supply'],['Streetlight',5,'Street Lighting'],
 ['Drainage',6,'Drainage'],['Electricity',7,'Electricity']
];
let user=null, mode='login', adminMode=false, page='overview', issues=[], notifications=[], dashboard={};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nice=s=>String(s||'').toLowerCase().replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
const toast=m=>{let t=$('#toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),3000)};
const count=s=>issues.filter(i=>i.status===s).length;
async function api(path, options={}) {
  const res=await fetch(API+path,options);
  const raw=await res.text(); let data;
  try{data=raw?JSON.parse(raw):null}catch{data=raw}
  if(!res.ok) throw new Error(data?.detail||data?.message||`API error ${res.status}`);
  return data;
}
function issueFromApi(x){
 const category=x.category_name||'Other';
 const dep=CATEGORIES.find(c=>c[0].toLowerCase()===category.toLowerCase())?.[2] || category;
 return {id:x.issue_id,code:x.issue_code,title:x.title,description:x.description,location:x.location,
   category,department:dep,priority:nice(x.priority),status:x.status,created:x.created_at?new Date(x.created_at).toLocaleDateString():'',support:null,owner:'Citizen'};
}
async function loadIssues(){
 const data=await api('/issues'); issues=(data||[]).map(issueFromApi);
}
async function loadDashboard(){try{dashboard=await api('/dashboard')}catch{dashboard={}}}
async function loadNotifications(){
 if(!user?.id){notifications=[];return}
 try{notifications=await api(`/users/${user.id}/notifications`)}catch(e){notifications=[];console.warn(e)}
}
function showAuth(m='login',a=false){
 mode=m;adminMode=a;$('#authView').classList.remove('hidden');$('#appView').classList.add('hidden');
 $('#authTabs').classList.toggle('hidden',a);
 $('#adminEntry').textContent=a?'← Citizen sign in':'Administrator access ↗';
 $('#authEyebrow').textContent=a?'ADMINISTRATOR SIGN IN':'CIVICTRACK · CONNECTED TO API';
 $('#authTitle').textContent=a?'Administrator sign in.':m==='register'?'Create your CivicTrack account.':'Make your community better.';
 $('#authSubtitle').textContent=a?'Use an existing authorized administrator account.':m==='register'?'Register with the details requested by the CivicTrack server.':'Sign in to report an issue or follow its progress.';
 $('#authSubmit').innerHTML=(m==='register'?'Create account':'Sign in')+' <span>→</span>';
 $('#registerFields').classList.toggle('hidden',m!=='register');
 ['full_name','phone','address'].forEach(n=>{const el=$(`[name="${n}"]`);if(el)el.required=(m==='register');});
 $('#authForm').reset();
 $$('[data-auth]').forEach(b=>b.classList.toggle('active',b.dataset.auth===m));
}
function enter(profile){
 user=profile;
 $('#authView').classList.add('hidden');$('#appView').classList.remove('hidden');
 $('#sideUserName').textContent=profile.name;$('#sideUserRole').textContent=profile.role==='ADMIN'?'Administrator':'Community member';
 $('#userAvatar').textContent=(profile.name||'U')[0].toUpperCase();$('#topAvatar').textContent=(profile.name||'U')[0].toUpperCase();
 $('#mainNav').innerHTML=nav();go(profile.role==='ADMIN'?'admin':'overview');
}
function nav(){
 let a=user.role==='ADMIN';
 let links=a?[['admin','⌂','Admin overview'],['admin-issues','▤','Manage complaints'],['unresolved','◷','Unresolved issues'],['departments','▦','Departments'],['notifications','♧','Notifications']]:
 [['overview','⌂','Overview'],['report','＋','Report an issue'],['explore','◉','Explore issues'],['unresolved','◷','Unresolved issues'],['my-issues','▤','My reports'],['departments','▦','Departments'],['notifications','♧','Notifications']];
 return links.map(([p,i,n])=>`<button class="nav-link ${page===p?'active':''}" data-page="${p}"><span>${i}</span>${n}${p==='unresolved'?`<i>${issues.filter(x=>!['RESOLVED','CLOSED','REJECTED'].includes(x.status)).length}</i>`:''}</button>`).join('');
}
function heading(title,sub,action=''){return `<div class="page-heading"><div><h1>${title}</h1><p>${sub}</p></div>${action?`<div class="heading-actions">${action}</div>`:''}</div>`}
function stat(label,value,icon,foot){return `<div class="stat-card"><div class="stat-top">${label}<span class="stat-icon">${icon}</span></div><div class="stat-value">${value??'—'}</div><div class="stat-foot">${foot}</div></div>`}
function status(s){return `<span class="status ${String(s).toLowerCase()}">${nice(s)}</span>`}
function issueCard(i){return `<article class="issue-card" data-detail="${i.id}"><div class="issue-card-top"><span class="eyebrow">${esc(i.category)}</span>${status(i.status)}</div><h3>${esc(i.title)}</h3><p>${esc(i.description)}</p><div class="issue-meta"><span>⌖ ${esc(i.location)}</span><span>◷ ${esc(i.created)}</span></div><div class="issue-card-foot"><small>${i.code?`Complaint ${esc(i.code)}`:'Live complaint record'}</small><button class="support" data-detail="${i.id}">View details</button></div></article>`}
function overview(){
 let open=dashboard.unresolved??issues.filter(i=>!['RESOLVED','CLOSED','REJECTED'].includes(i.status)).length;
 return heading(`Good day, ${esc((user.name||'Citizen').split(' ')[0])} 👋`,'Here is what is happening in your community today.',`<button class="btn btn-primary" data-go="report">＋ Report an issue</button>`)
 +`<div class="stats-grid">${stat('Total community reports',dashboard.total_complaints??issues.length,'▤','Across all departments')}${stat('Awaiting attention',open,'◷','Issues still being addressed')}${stat('Resolved issues',dashboard.resolved??count('RESOLVED'),'✓','Marked as resolved')}${stat('In progress',dashboard.in_progress??count('IN_PROGRESS'),'↻','Being addressed')}</div>
 <div class="content-grid"><section class="panel"><div class="panel-head"><h3>Recent community reports</h3><button class="small-link" data-go="explore">View all →</button></div>${issues.slice(0,5).map(i=>`<div class="issue-row" data-detail="${i.id}"><div class="issue-symbol">${DEPTS.find(d=>d[0]===i.department)?.[1]||'📍'}</div><div class="issue-row-main"><b>${esc(i.title)}</b><small>${esc(i.location)}</small></div>${status(i.status)}</div>`).join('')||'<p class="muted">No complaints have been submitted yet.</p>'}</section>
 <section class="panel"><div class="panel-head"><h3>Quick actions</h3></div><div class="quick-actions"><button class="quick-action" data-go="report"><span class="qa-icon">＋</span><strong>Report an issue</strong><small>Tell us what needs attention</small></button><button class="quick-action" data-go="unresolved"><span class="qa-icon">◷</span><strong>Unresolved issues</strong><small>See what still needs action</small></button><button class="quick-action" data-go="departments"><span class="qa-icon">▦</span><strong>Departments</strong><small>Find the right civic team</small></button><button class="quick-action" data-go="my-issues"><span class="qa-icon">▤</span><strong>My reports</strong><small>View reports from the API</small></button></div></section></div>`;
}
function listing(title,sub,filter){
 let arr=filter(issues);
 return heading(title,sub)+`<div class="toolbar"><input id="searchIssues" placeholder="Search by issue or location…"><select id="filterDept"><option value="">All departments</option>${DEPTS.map(d=>`<option>${d[0]}</option>`).join('')}</select><select id="filterStatus"><option value="">All statuses</option>${['SUBMITTED','UNDER_REVIEW','ASSIGNED','IN_PROGRESS','RESOLVED','CLOSED','REJECTED'].map(s=>`<option value="${s}">${nice(s)}</option>`).join('')}</select></div><div class="issue-grid" id="issueGrid">${arr.map(issueCard).join('')||'<div class="empty">No issues match your filters.</div>'}</div>`;
}
function report(){
 return heading('Report a civic issue','Your report will be submitted to the connected CivicTrack backend.')
 +`<div class="form-layout"><form class="form-panel" id="reportForm"><h3>Issue details</h3><p>Fields marked with * are required.</p>
 <label>Issue title *<input name="title" required maxlength="200" placeholder="e.g. Pothole near the bus stop"></label>
 <div class="two-fields"><label>Category *<select name="category_id" required><option value="">Choose category</option>${CATEGORIES.map(c=>`<option value="${c[1]}">${c[0]} — ${c[2]}</option>`).join('')}</select></label>
 <label>Priority<select name="priority"><option value="MEDIUM">Medium</option><option value="LOW">Low</option><option value="HIGH">High</option><option value="CRITICAL">Critical</option></select></label></div>
 <label>Location *<input name="location" required maxlength="255" placeholder="Street, landmark, ward or area"></label>
 <label>Description *<textarea name="description" required minlength="12" placeholder="Tell us what happened and why it needs attention…"></textarea></label>
 <label>Attach a photo (optional)<div class="upload-box">📷 Add a JPG, PNG or WebP photo (max 5 MB)<input name="photo" type="file" accept="image/jpeg,image/png,image/webp"></div></label>
 <button class="btn btn-primary">Submit report →</button></form>
 <aside><div class="tip-card"><b>✳ What happens next?</b><p>Your report is saved by the CivicTrack API. The department can review and update its progress.</p></div><div class="tip-card"><b>🔎 Be specific</b><p>Add a nearby landmark and a clear description.</p></div><div class="tip-card"><b>ℹ Existing API limitation</b><p>Citizen support counts and department/category lookup endpoints are not provided by this backend.</p></div></aside></div>`;
}
function departments(){
 return heading('Civic departments','Departments are shown from the categories seeded in the supplied SQL script.')
 +`<div class="dept-grid">${DEPTS.map(d=>`<article class="dept-card"><div class="dept-icon">${d[1]}</div><h3>${d[0]}</h3><p>${d[2]}</p><button data-dept="${d[0]}">View related issues →</button></article>`).join('')}</div>`;
}
function admin(){
 return heading('Administration overview','Live statistics returned by the supplied backend.')
 +`<div class="stats-grid">${stat('Total reports',dashboard.total_complaints??issues.length,'▤','All submitted issues')}${stat('Awaiting action',dashboard.unresolved??'—','◷','Open or in progress')}${stat('Resolved',dashboard.resolved??'—','✓','Resolved reports')}${stat('In progress',dashboard.in_progress??'—','↻','Being addressed')}</div>
 <section class="panel"><div class="panel-head"><h3>Complaint management</h3><button class="small-link" data-go="admin-issues">Manage all →</button></div>${issues.slice(0,6).map(i=>`<div class="issue-row" data-detail="${i.id}"><div class="issue-row-main"><b>${esc(i.title)}</b><small>${esc(i.code||'')} · ${esc(i.department)}</small></div>${status(i.status)}</div>`).join('')||'<p class="muted">No complaints available.</p>'}</section>
 <p class="muted">Important: the supplied backend does not enforce admin roles on its update endpoints. This dashboard is not secure for public deployment without backend authorization.</p>`;
}
function render(){
 let content='';
 if(page==='overview')content=overview();
 else if(page==='report')content=report();
 else if(page==='explore')content=listing('Explore community issues','Live complaints returned by the backend.',a=>a);
 else if(page==='unresolved')content=listing('Unresolved issues','Reports that still need attention.',a=>a.filter(i=>!['RESOLVED','CLOSED','REJECTED'].includes(i.status)));
 else if(page==='my-issues')content=heading('My reports','The current API does not return user ownership in its issue-list response.')+`<section class="panel"><p>For privacy and accuracy, this page cannot reliably filter your reports using the supplied endpoints. You can still view all community reports under Explore issues.</p><button class="btn btn-primary" data-go="explore">Explore community issues</button></section>`;
 else if(page==='departments')content=departments();
 else if(page==='notifications')
    content=heading('Notifications','Updates returned by the backend.')
    + `<section class="panel">
        ${notifications.map(n=>`
            <div class="notification">
                <div class="notification-icon">♧</div>
                <div>
                    <b>${esc(n.message)}</b>
                    <p>Complaint ID: ${esc(n.issue_id??'—')}</p>
                    <small>
                        ${n.created_at ? new Date(n.created_at).toLocaleString() : ''}
                        ${n.is_read ? '· Read' : '· Unread'}
                    </small>

                    ${!n.is_read ? `
                        <button class="btn btn-secondary"
                            data-mark-read="${n.notification_id}">
                            Mark as Read
                        </button>
                    ` : ''}
                </div>
            </div>
        `).join('') || '<p class="muted">No notifications returned for this account.</p>'}
    </section>`;
 else if(page==='admin')content=admin();
 else if(page==='admin-issues')content=heading('Manage complaints','Select a complaint to update its status or department.')+`<div class="panel"><div class="table-wrap"><table class="data-table"><thead><tr><th>Complaint</th><th>Category</th><th>Priority</th><th>Status</th><th>Action</th></tr></thead><tbody>${issues.map(i=>`<tr><td><b>${esc(i.title)}</b><br><small>${esc(i.code||i.id)}</small></td><td>${esc(i.category)}</td><td>${esc(i.priority)}</td><td>${status(i.status)}</td><td><button data-detail="${i.id}">Manage</button></td></tr>`).join('')}</tbody></table></div></div>`;
 $('#pageContent').innerHTML=content;
 $('#breadcrumb').textContent=({'overview':'Overview','report':'Report an issue','explore':'Explore issues','unresolved':'Unresolved issues','my-issues':'My reports','departments':'Departments','notifications':'Notifications','admin':'Admin overview','admin-issues':'Manage complaints'})[page]||page;
 $('#mainNav').innerHTML=nav();
}
async function refresh(){await loadIssues();await loadDashboard();await loadNotifications();render()}
function go(p){page=p;render();$('#sidebar').classList.remove('open');window.scrollTo(0,0)}
function detail(id){
 let i=issues.find(x=>x.id===Number(id));if(!i)return;
 let box=document.createElement('div');box.className='modal-backdrop';box.id='detailModal';
 box.innerHTML=`<div class="modal"><div class="modal-head"><h2>${esc(i.title)}</h2><button class="modal-close" data-dismiss>×</button></div>
 <p>${esc(i.description)}</p><div class="issue-meta"><span>⌖ ${esc(i.location)}</span><span>Category: ${esc(i.category)}</span><span>Priority: ${esc(i.priority)}</span></div>
 <p>Complaint: <b>${esc(i.code||i.id)}</b></p><p>Current status: ${status(i.status)}</p>
 ${user.role==='ADMIN'?`<label>Update status<select id="adminStatus">${['SUBMITTED','UNDER_REVIEW','ASSIGNED','IN_PROGRESS','RESOLVED','CLOSED','REJECTED'].map(s=>`<option ${i.status===s?'selected':''} value="${s}">${nice(s)}</option>`).join('')}</select></label><label>Assign department<select id="adminDept">${DEPTS.map(d=>`<option value="${d[3]}" ${i.department===d[0]?'selected':''}>${d[0]}</option>`).join('')}</select></label><button class="btn btn-primary" data-save="${i.id}">Save status</button><button class="btn btn-secondary" data-assign="${i.id}">Assign department</button>`:''}
 <div class="modal-actions"><button class="btn btn-outline" data-dismiss>Close</button></div></div>`;
 document.body.append(box);
}
$('#authTabs').addEventListener('click',e=>{let b=e.target.closest('[data-auth]');if(b)showAuth(b.dataset.auth)});
$('#adminEntry').onclick=()=>showAuth('login',!adminMode);
$('#checkApi').onclick=async()=>{let el=$('#apiStatus');el.textContent='Checking…';try{await api('/');el.textContent='Backend reachable at '+API;toast('Backend connection successful')}catch(e){el.textContent='Connection failed: '+e.message;toast('Cannot reach backend: '+e.message)}};
$('#authForm').onsubmit=async e=>{
 e.preventDefault();let f=new FormData(e.target),button=$('#authSubmit');button.disabled=true;
 try{
  if(mode==='register'){
   const body={full_name:f.get('full_name'),email:f.get('email'),phone:f.get('phone'),password:f.get('password'),address:f.get('address')};
   const r=await api('/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   toast(r.message||'Registration successful. You can now sign in.');showAuth('login');return;
  }
  const r=await api('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:f.get('email'),password:f.get('password')})});
  const role=String(r.role||'CITIZEN').toUpperCase();
  if(adminMode&&role!=='ADMIN')throw new Error('This account is not an administrator.');
  if(!adminMode&&role==='ADMIN')throw new Error('Please use Administrator access for this account.');
  user={id:r.user_id,role,name:r.full_name,email:f.get('email')};
  await refresh();enter(user);toast('Signed in to CivicTrack API');
 }catch(err){toast(err.message||'Request failed')}finally{button.disabled=false}
};
$('#mainNav').onclick=e=>{let b=e.target.closest('[data-page]');if(b)go(b.dataset.page)};
document.addEventListener('click',async e=>{
 const modalButton=e.target.closest('[data-save],[data-assign],[data-dismiss]');
 if(!modalButton || !modalButton.closest('#detailModal')) return;
 if(modalButton.hasAttribute('data-dismiss')) { $('#detailModal')?.remove(); return; }
 if(modalButton.dataset.save) {
  try { await api(`/issues/${modalButton.dataset.save}/status?status=${encodeURIComponent($('#adminStatus').value)}&updated_by=${user.id}`,{method:'PATCH'}); $('#detailModal').remove(); await refresh(); toast('Status updated in database'); }
  catch(err){ toast('Update failed: '+err.message); }
 }
 if(modalButton.dataset.assign) {
  try { await api(`/issues/${modalButton.dataset.assign}/department?department_id=${encodeURIComponent($('#adminDept').value)}&assigned_by=${user.id}`,{method:'PATCH'}); $('#detailModal').remove(); await refresh(); toast('Department assignment saved'); }
  catch(err){ toast('Assignment failed: '+err.message); }
 }
});
$('#pageContent').onclick=async e=>{
let b=e.target.closest('[data-go],[data-detail],[data-dept],[data-dismiss],[data-save],[data-mark-read]');
if(!b)return;

if(b.dataset.markRead){
    try{
        await api(`/notifications/${b.dataset.markRead}/read`,{
            method:'PATCH'
        });

        await loadNotifications();
        render();

        toast('Notification marked as read');
    }
    catch(err){
        toast('Failed to mark as read: '+err.message);
    }
    return;
}
 if(b.dataset.go)go(b.dataset.go);
 if(b.dataset.detail)detail(b.dataset.detail);
 if(b.dataset.dept){go('explore');setTimeout(()=>{let s=$('#filterDept');if(s){s.value=b.dataset.dept;s.dispatchEvent(new Event('change'))}},0)}
 if(b.hasAttribute('data-dismiss'))$('#detailModal')?.remove();
 if(b.dataset.save){
  try{await api(`/issues/${b.dataset.save}/status?status=${encodeURIComponent($('#adminStatus').value)}&updated_by=${user.id}`,{method:'PATCH'});$('#detailModal').remove();await refresh();toast('Status updated in database')}
  catch(err){toast('Update failed: '+err.message)}
 }
};
$('#pageContent').onsubmit=async e=>{
 if(e.target.id!=='reportForm')return;e.preventDefault();
 let f=new FormData(e.target),file=f.get('photo');
 try{
  const payload={user_id:user.id,category_id:Number(f.get('category_id')),title:f.get('title'),description:f.get('description'),location:f.get('location'),priority:f.get('priority')};
  const result=await api('/issues',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  await refresh();
  if(file&&file.size){
   const created=issues.find(x=>x.code===result.complaint_id);
   if(created){const fd=new FormData();fd.append('file',file);await api(`/issues/${created.id}/images`,{method:'POST',body:fd});}
   else toast('Complaint saved, but image could not be linked because the API response did not identify the new numeric issue ID.');
  }
  toast(`Complaint submitted: ${result.complaint_id||''}`);await refresh();go('explore');
 }catch(err){toast('Submission failed: '+err.message)}
};
$('#pageContent').oninput=e=>{if(e.target.id==='searchIssues')filterIssues()};
$('#pageContent').onchange=e=>{if(['filterDept','filterStatus'].includes(e.target.id))filterIssues()};
function filterIssues(){
 let q=($('#searchIssues')?.value||'').toLowerCase(),d=$('#filterDept')?.value||'',s=$('#filterStatus')?.value||'';
 let grid=$('#issueGrid');if(!grid)return;
 [...grid.querySelectorAll('.issue-card')].forEach(card=>{let i=issues.find(x=>x.id===Number(card.dataset.detail));card.style.display=(!q||`${i.title} ${i.location}`.toLowerCase().includes(q))&&(!d||i.department===d)&&(!s||i.status===s)?'':'none'});
}
$('#logoutButton').onclick=()=>{user=null;issues=[];notifications=[];showAuth()};
$('#menuButton').onclick=()=>$('#sidebar').classList.toggle('open');
$('#sidebarClose').onclick=()=>$('#sidebar').classList.remove('open');
$('#topNotifications').onclick=()=>go('notifications');
$('#profileButton').onclick=()=>toast(user?.email||'');
