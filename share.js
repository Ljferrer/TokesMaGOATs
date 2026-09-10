/* Local PNG snapshots. html-to-image 1.11.13 is bundled under vendor/. */
(() => {
  let exporting = false;
  async function saveSnapshot(target, title, button) {
    if (exporting) return;
    exporting = true;
    const previous = button.textContent;
    button.disabled = true;
    button.textContent = 'Rendering…';
    let frame;
    try {
      if (!window.htmlToImage) throw new Error('Image library unavailable. Reload and try again.');
      await document.fonts.ready;
      frame = document.createElement('div');
      frame.className = 'snapshot-frame';
      frame.style.cssText = 'position:fixed;left:-20000px;top:0;width:1200px;padding:32px;background:#101411;color:#e7eadc;';
      const heading = document.createElement('div');
      heading.className = 'snapshot-heading';
      heading.textContent = 'TokesMaGOATs / '+title;
      const context = document.createElement('p');
      context.className = 'muted';
      context.textContent = 'Selected year: '+document.getElementById('year').value+' · Captured '+new Date().toLocaleString();
      const clone = target.cloneNode(true);
      // Freeze SVG presentation explicitly; nested SVG image rendering otherwise
      // loses inherited page CSS (notably axis labels and grid lines).
      const sourceSvg = target.querySelectorAll('svg,svg *');
      clone.querySelectorAll('svg,svg *').forEach((node,i) => {
        const computed = getComputedStyle(sourceSvg[i]);
        for (const property of ['fill','stroke','stroke-width','stroke-dasharray','opacity','font-family','font-size','font-weight','text-anchor']) {
          node.style.setProperty(property,computed.getPropertyValue(property));
        }
      });
      // Freeze controls to their selected labels, and omit action buttons.
      const originalSelects = target.querySelectorAll('select');
      clone.querySelectorAll('select').forEach((select,i) => {
        const label = document.createElement('span');
        label.textContent = originalSelects[i].selectedOptions[0]?.textContent || originalSelects[i].value;
        select.replaceWith(label);
      });
      clone.querySelectorAll('[data-snapshot-ignore],button:not(.day)').forEach(node => node.remove());
      clone.querySelectorAll('.chart-scroll,.gridwrap,#detail').forEach(node => {
        node.style.overflow = 'visible';
        node.style.maxWidth = 'none';
      });
      // Size for readable exports regardless of the browser's viewport.
      clone.style.width = '100%';
      clone.style.margin = '0';
      const foot = document.createElement('p');
      foot.className = 'muted';
      foot.textContent = 'Recorded input + output, including cached input · Carbon values are estimates.';
      frame.append(heading,context,clone,foot);
      document.body.append(frame);
      const width = Math.ceil(Math.max(1200,frame.scrollWidth));
      const height = Math.ceil(frame.scrollHeight);
      // Bound canvas area for very tall snapshots with expanded ledgers.
      const pixelRatio = Math.min(2,Math.sqrt(24000000/(width*height)),16000/Math.max(width,height));
      const blob = await window.htmlToImage.toBlob(frame, {
        backgroundColor:'#101411',width,height,pixelRatio,skipFonts:true,
        style:{position:'static',left:'auto',top:'auto'},
      });
      if (!blob) throw new Error('Image could not be generated.');
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'TokesMaGOATs-'+title.toLowerCase().replace(/[^a-z0-9]+/g,'-')+'-'+document.getElementById('year').value+'.png';
      document.body.append(link);link.click();link.remove();
      setTimeout(() => URL.revokeObjectURL(url),60000);
      document.getElementById('status').textContent = 'PNG ready: '+title+'.';
    } catch (error) {
      document.getElementById('status').textContent = 'Snapshot failed: '+error.message;
    } finally {
      frame?.remove();button.disabled=false;button.textContent=previous;exporting=false;
    }
  }
  function addButton(target,title,host) {
    const button=document.createElement('button');
    button.className='snapshot-button';button.textContent='↓ Save PNG';
    button.dataset.snapshotIgnore='';button.type='button';
    button.setAttribute('aria-label','Save '+title+' as PNG');
    button.title='Download a shareable image';
    button.onclick=()=>saveSnapshot(target,title,button);
    host.append(button);
  }
  const main=document.querySelector('main');
  const header=document.querySelector('header');
  addButton(main,'Dashboard',header);
  header.insertBefore(header.querySelector('.snapshot-button'),header.querySelector('button'));
  document.querySelectorAll('section.panel').forEach(panel=>{
    const heading=panel.querySelector('h2');
    if (!heading || panel.querySelector('#coverage')) return;
    const title=heading.childNodes[0].textContent.trim();
    const actions=document.createElement('div');actions.className='snapshot-actions';actions.dataset.snapshotIgnore='';
    addButton(panel,title,actions);panel.prepend(actions);
  });
  // The selected day's pie can also be shared independently of the activity grid.
  const day=document.getElementById('dayBreakdown');
  const actions=document.createElement('div');actions.className='snapshot-actions';actions.dataset.snapshotIgnore='';
  const button=document.createElement('button');button.className='snapshot-button';button.textContent='↓ Save day PNG';
  button.onclick=()=>saveSnapshot(day,'Day '+document.getElementById('dayDate').textContent,button);
  actions.append(button);day.append(actions);
})();
