function setTheme(theme){document.body.dataset.theme=theme==='light'?'light':'dark';try{localStorage.setItem('tt-theme',document.body.dataset.theme);}catch{}if(typeof window.pywebview?.api?.save_theme==='function')window.pywebview.api.save_theme(document.body.dataset.theme).catch(()=>{});}
try{setTheme(localStorage.getItem('tt-theme')||'dark');}catch{setTheme('dark');}
$('theme-toggle').addEventListener('click',()=>setTheme(document.body.dataset.theme==='dark'?'light':'dark'));
async function initializeNative(){document.body.classList.add('desktop');$('native-titlebar').hidden=false;$('output-folder-settings').hidden=false;await refreshOutputFolder();try{let settings=await window.pywebview.api.load_settings();if(settings.theme)setTheme(settings.theme);if(settings.options){let o=settings.options;$('codes').value=o.codes.join(', ');$('good').value=o.good;$('bad').value=o.bad;$('mode').value=o.mode;for(const[id,key]of[['exclude-unknown','excludeUnknown'],['journal','journal'],['outline','outline']])$(id).checked=o[key];$('selected-count').textContent='Выбрано: '+o.codes.length;applyMode();}}catch{}}
window.addEventListener('pywebviewready',initializeNative);if(typeof window.pywebview?.api?.load_settings==='function')initializeNative();
for(const id of ['codes','good','bad','exclude-unknown','journal','outline','mode'])$(id).addEventListener('change',()=>{if(window.pywebview?.api)window.pywebview.api.save_options(opts());});
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
