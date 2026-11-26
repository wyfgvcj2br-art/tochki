let nativeReady=false,nativeStarted=false,migrationToken=null;
function setTheme(theme){document.body.dataset.theme=theme==='light'?'light':'dark';try{localStorage.setItem('tt-theme',document.body.dataset.theme);}catch{}if(nativeReady&&typeof window.pywebview?.api?.save_theme==='function')window.pywebview.api.save_theme(document.body.dataset.theme).catch(e=>notice(e.message,'error'));}
try{setTheme(localStorage.getItem('tt-theme')||'dark');}catch{setTheme('dark');}
$('theme-toggle').addEventListener('click',()=>setTheme(document.body.dataset.theme==='dark'?'light':'dark'));
async function applyNativeSettings(){
 try{
  const settings=await window.pywebview.api.load_settings();
  if(settings.theme)setTheme(settings.theme);
  if(settings.options){
   const o=settings.options;
   if(Array.isArray(o.codes))$('codes').value=o.codes.join(', ');
   for(const id of ['good','bad','mode'])if(o[id]!==undefined)$(id).value=o[id];
   for(const[id,key]of[['exclude-unknown','excludeUnknown'],['journal','journal'],['outline','outline']])if(o[key]!==undefined)$(id).checked=o[key];
   $('selected-count').textContent='Выбрано: '+opts().codes.length;applyMode();
  }
 }catch(e){notice(e.message||'Не удалось прочитать настройки. Файл сохранён.','error');}
 await refreshOutputFolder();
}
async function initializeNative(){
 if(nativeStarted)return;nativeStarted=true;
 document.body.classList.add('desktop');$('native-titlebar').hidden=false;$('output-folder-settings').hidden=false;
 const info=await window.pywebview.api.get_app_info();
 $('product-version').textContent='Версия '+info.version+(info.mode==='portable'?' · Portable':'');
 document.querySelector('.native-subtitle').textContent=info.mode==='portable'?'/ PORTABLE':'/ DESKTOP';
 await applyNativeSettings();
 const migration=await window.pywebview.api.get_migration_status();
 $('migration-open').hidden=!migration.available;
 if(migration.pending)$('migration-dialog').showModal();
 nativeReady=true;
}
window.addEventListener('pywebviewready',initializeNative);if(typeof window.pywebview?.api?.load_settings==='function')initializeNative();
for(const id of ['codes','good','bad','exclude-unknown','journal','outline','mode'])$(id).addEventListener('change',()=>{if(nativeReady&&window.pywebview?.api)window.pywebview.api.save_options(opts()).catch(e=>notice(e.message,'error'));});
$('win-min').addEventListener('click',()=>window.pywebview?.api.minimize());$('win-max').addEventListener('click',()=>window.pywebview?.api.maximize());$('win-close').addEventListener('click',()=>window.pywebview?.api.close());
$('image-list').addEventListener('click',e=>{const link=e.target.closest('a');if(!link)return;e.preventDefault();$('image-preview').src=link.href;$('image-modal').hidden=false;$('image-close').focus();});
function closeImage(){$('image-modal').hidden=true;$('image-preview').removeAttribute('src');}
$('image-close').addEventListener('click',closeImage);$('image-modal').addEventListener('click',e=>{if(e.target===$('image-modal'))closeImage();});document.addEventListener('keydown',e=>{if(e.key==='Escape')closeImage();});

function showOutputFolder(value){
 if(value.error)throw Error(value.error);
 if(value.path){$('output-folder-path').textContent=value.path;$('output-folder-path').title=value.path;}
}
async function refreshOutputFolder(){
 try{showOutputFolder(await window.pywebview.api.get_output_folder());}
 catch(e){$('output-folder-status').textContent=e.message||'Не удалось прочитать папку отчётов.';}
}
$('choose-output-folder').addEventListener('click',async()=>{
 if(busy)return;
 const button=$('choose-output-folder');button.disabled=true;$('output-folder-status').textContent='';
 try{
  const folder=await window.pywebview.api.choose_output_folder();showOutputFolder(folder);
  if(!folder.cancelled)$('output-folder-status').textContent='Папка сохранена. Следующие отчёты появятся здесь.';
 }catch(e){$('output-folder-status').textContent=e.message||'Не удалось выбрать папку.';}
 finally{button.disabled=busy;}
});
$('open-output-folder').addEventListener('click',async()=>{
 try{const response=await window.pywebview.api.open_output_folder();if(response.error)throw Error(response.error);}
 catch(e){$('output-folder-status').textContent=e.message||'Не удалось открыть папку.';}
});

$('migration-open').addEventListener('click',()=>{$('migration-dialog').showModal();});
$('migration-dialog').addEventListener('cancel',e=>e.preventDefault());
$('migration-choose').addEventListener('click',async()=>{
 try{
  const result=await window.pywebview.api.choose_portable_folder();
  if(result.error)throw Error(result.error);if(result.cancelled)return;
  migrationToken=result.token;$('migration-status').textContent=result.source;
  $('migration-files').replaceChildren();
  for(const file of result.files){
   const row=document.createElement('p');row.textContent=file.name+(file.replace?' — будет заменён после подтверждения; текущая версия сохранится в резервной копии':' — будет добавлен');
   $('migration-files').append(row);
  }
  $('migration-import').disabled=false;
 }catch(e){migrationToken=null;$('migration-import').disabled=true;$('migration-status').textContent=e.message;}
});
$('migration-skip').addEventListener('click',async()=>{
 try{await window.pywebview.api.skip_migration();$('migration-dialog').close();}
 catch(e){$('migration-status').textContent=e.message;}
});
$('migration-import').addEventListener('click',async()=>{
 const button=$('migration-import');button.disabled=true;$('migration-choose').disabled=true;$('migration-skip').disabled=true;
 try{
  const result=await window.pywebview.api.import_portable(migrationToken);
  if(result.error)throw Error(result.error);if(result.cancelled)return;
  nativeReady=false;await applyNativeSettings();nativeReady=true;
  $('migration-dialog').close();notice('Настройки и справочник импортированы.'+(result.backup?' Резервная копия: '+result.backup:''));migrationToken=null;
 }catch(e){$('migration-status').textContent=e.message;}
 finally{button.disabled=!migrationToken;$('migration-choose').disabled=false;$('migration-skip').disabled=false;}
});
