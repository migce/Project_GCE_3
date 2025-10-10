/* Simple reusable modal + rules flowchart renderer for Project GCE 3 */
(function(global){
  function parseRules(text){
    if(!text) return [];
    var lines = text.split(/\r?\n/).map(function(s){return s.trim();}).filter(Boolean);
    var rules = [];
    lines.forEach(function(line){
      var s = line.replace(/^IF\s+/i,'');
      var thenIdx = s.toUpperCase().indexOf(' THEN ');
      if(thenIdx < 0){ return; }
      var cond = s.slice(0, thenIdx).trim();
      var rest = s.slice(thenIdx + 6).trim();
      var elseIdx = rest.toUpperCase().indexOf(' ELSE ');
      var thenPart = elseIdx >= 0 ? rest.slice(0, elseIdx).trim() : rest;
      var elsePart = elseIdx >= 0 ? rest.slice(elseIdx + 6).trim() : '';

      function splitActs(part){
        if(!part) return [];
        // remove optional surrounding braces
        if(part.startsWith('{') && part.endsWith('}')){
          part = part.slice(1, -1);
        }
        // allow separators ; , +
        return part.split(/[;,\+]/).map(function(x){return x.trim();}).filter(Boolean);
      }
      rules.push({ condition: cond, thenActs: splitActs(thenPart), elseActs: splitActs(elsePart) });
    });
    return rules;
  }

  function el(tag, cls, text){
    var e = document.createElement(tag);
    if(cls) e.className = cls;
    if(text != null) e.textContent = text;
    return e;
  }

  function render(rules, root){
    root.innerHTML = '';
    if(!rules || !rules.length){
      root.appendChild(el('div', null, 'No rules to display.'));
      return;
    }
    rules.forEach(function(r){
      // Container
      var box = el('div', 'gce-scheme');
      var grid = el('div', 'gce-scheme-grid');
      box.appendChild(grid);

      // Nodes
      var decision = el('div', 'gce-node decision');
      decision.appendChild(el('div', 'label', 'IF'));
      decision.appendChild(el('div', null, r.condition || '(condition)'));
      grid.appendChild(decision);

      var thenNode = el('div', 'gce-node then');
      thenNode.appendChild(el('div', 'label', 'THEN'));
      var thenActs = el('div', 'gce-actions');
      (r.thenActs && r.thenActs.length ? r.thenActs : ['NONE']).forEach(function(a){
        thenActs.appendChild(el('span', 'gce-chip', a));
      });
      thenNode.appendChild(thenActs);
      grid.appendChild(thenNode);

      var elseNode = null;
      if(r.elseActs && r.elseActs.length){
        elseNode = el('div', 'gce-node else');
        elseNode.appendChild(el('div', 'label', 'ELSE'));
        var elseActs = el('div', 'gce-actions');
        r.elseActs.forEach(function(a){ elseActs.appendChild(el('span', 'gce-chip', a)); });
        elseNode.appendChild(elseActs);
        grid.appendChild(elseNode);
      } else {
        // Center THEN if no ELSE
        thenNode.classList.add('center');
      }

      // SVG connectors overlay
      var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.classList.add('gce-scheme-svg');
      svg.setAttribute('width', '100%');
      svg.setAttribute('height', '100%');
      // Arrow marker
      var defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      var marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
      marker.setAttribute('id', 'gce-arrow');
      marker.setAttribute('viewBox', '0 0 10 10');
      marker.setAttribute('refX', '10');
      marker.setAttribute('refY', '5');
      marker.setAttribute('markerWidth', '6');
      marker.setAttribute('markerHeight', '6');
      marker.setAttribute('orient', 'auto-start-reverse');
      var tri = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      tri.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
      tri.setAttribute('fill', '#764ba2');
      marker.appendChild(tri);
      defs.appendChild(marker);
      svg.appendChild(defs);
      box.appendChild(svg);

      function centerRight(el){
        var r = el.getBoundingClientRect();
        var p = box.getBoundingClientRect();
        return { x: r.right - p.left, y: r.top - p.top + r.height/2 };
      }
      function centerLeft(el){
        var r = el.getBoundingClientRect();
        var p = box.getBoundingClientRect();
        return { x: r.left - p.left, y: r.top - p.top + r.height/2 };
      }
      function centerBottom(el){
        var r = el.getBoundingClientRect();
        var p = box.getBoundingClientRect();
        return { x: r.left - p.left + r.width/2, y: r.bottom - p.top };
      }
      function centerTop(el){
        var r = el.getBoundingClientRect();
        var p = box.getBoundingClientRect();
        return { x: r.left - p.left + r.width/2, y: r.top - p.top };
      }
      function line(p1, p2){
        var e = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        var midX = (p1.x + p2.x)/2;
        // smooth curve
        var d = 'M'+p1.x+','+p1.y+' C '+midX+','+p1.y+' '+midX+','+p2.y+' '+p2.x+','+p2.y;
        e.setAttribute('d', d);
        e.setAttribute('class', 'gce-arrow');
        e.setAttribute('marker-end', 'url(#gce-arrow)');
        return e;
      }

      // Defer drawing after layout
      setTimeout(function(){
        while(svg.firstChild && svg.firstChild.tagName !== 'defs') svg.removeChild(svg.firstChild);
        var from = centerBottom(decision);
        if(elseNode){
          svg.appendChild(line(from, centerTop(thenNode)));
          svg.appendChild(line(from, centerTop(elseNode)));
        } else {
          svg.appendChild(line(from, centerTop(thenNode)));
        }
      }, 0);

      root.appendChild(box);
    });
  }

  function openWithRules(title, rulesText){
    var overlay = document.getElementById('flowModalOverlay');
    var canvas = document.getElementById('flowModalCanvas');
    if(!overlay || !canvas) return;
    var tt = overlay.querySelector('.gce-modal-title');
    if(tt) tt.textContent = title || 'Rules Flowchart';
    render(parseRules(rulesText || ''), canvas);
    overlay.style.display = 'block';
  }

  global.FlowModal = {
    open: openWithRules,
    openFromElement: function(title, elOrSelector){
      var el = (typeof elOrSelector === 'string') ? document.querySelector(elOrSelector) : elOrSelector;
      var txt = el ? (el.textContent || el.value || '') : '';
      openWithRules(title, txt);
    }
  };
})(window);
