(function(){
  'use strict';
  
  /* ========================================
   * FAQ Accordion Toggle
   * ======================================== */
  document.addEventListener('click', function(e){
    var btn = e.target.closest('.ssyc-faq-toggle');
    if (!btn) return;
    
    var isOpen = btn.getAttribute('aria-expanded') === 'true';
    var answer = btn.parentElement.querySelector('.ssyc-faq-answer');
    
    if (isOpen) {
      btn.setAttribute('aria-expanded', 'false');
      if (answer) answer.setAttribute('hidden', '');
    } else {
      btn.setAttribute('aria-expanded', 'true');
      if (answer) answer.removeAttribute('hidden');
    }
  });
  
  /* ========================================
   * Leaflet Map Initialization
   * ======================================== */
  function initSSYCMaps(){
    if (!window.L) return;
    
    var els = document.querySelectorAll('.ssyc-map-geojson, .ssi-map-geojson');
    if (!els.length) return;
    
    els.forEach(function(el){
      if (el.__ssyc_map) return; // Already initialized
      
      try {
        var data = el.getAttribute('data-geojson');
        var json = data ? JSON.parse(data) : null;
        if (!json) return;
        
        var theme = el.getAttribute('data-theme') || 'light';
        var autofit = el.getAttribute('data-autofit') === '1';
        
        var map = L.map(el, { 
          zoomControl: true, 
          attributionControl: true 
        });
        el.__ssyc_map = map;
        
        // Tile layer based on theme
        var tileUrl = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
        if (theme === 'dark') {
          tileUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
        } else if (theme === 'satellite') {
          tileUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
        }
        
        L.tileLayer(tileUrl, { 
          maxZoom: 19, 
          attribution: '&copy; OpenStreetMap contributors' 
        }).addTo(map);
        
        // Add GeoJSON layer
        var layer = L.geoJSON(json, { 
          style: { 
            color: '#0ea5e9', 
            weight: 3, 
            opacity: 0.9 
          } 
        }).addTo(map);
        
        // Auto-fit bounds
        var bounds = layer.getBounds();
        if (bounds.isValid() && autofit) {
          map.fitBounds(bounds.pad(0.15));
        }
        
        // Extract points for markers
        var featurePoints = [];
        var linePoints = [];
        
        try {
          (json.features || []).forEach(function(f){
            if (!f || !f.geometry) return;
            
            if (f.geometry.type === 'LineString' && Array.isArray(f.geometry.coordinates)){
              f.geometry.coordinates.forEach(function(c){
                if (Array.isArray(c) && c.length >= 2) {
                  linePoints.push([c[1], c[0]]);
                }
              });
            } else if (f.geometry.type === 'Point' && Array.isArray(f.geometry.coordinates)){
              var latlng = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
              var props = f.properties || {};
              var label = props.label || props.name || '';
              featurePoints.push({ latlng: latlng, label: label });
            }
          });
        } catch (err) {}
        
        // Add markers (prefer labeled Point features, fallback to LineString vertices)
        var markersData = featurePoints.length > 0 ? featurePoints : linePoints.map(function(ll){
          return { latlng: ll, label: '' };
        });
        
        markersData.forEach(function(p, idx){
          var marker = L.marker(p.latlng, { 
            icon: L.divIcon({ 
              className: 'ssyc-pt', 
              html: '<div class="ssyc-pt-i">' + (idx + 1) + '</div>', 
              iconSize: [26, 26], 
              iconAnchor: [13, 13] 
            }) 
          }).addTo(map);
          
          if (p.label) {
            marker.bindTooltip((idx + 1) + '. ' + p.label, {
              permanent: false,
              direction: 'top',
              offset: [0, -12],
              opacity: 0.9
            });
          }
        });
        
        // Calculate total distance (haversine)
        var pathPoints = linePoints.length > 1 ? linePoints : (featurePoints.length > 1 ? featurePoints.map(function(p){return p.latlng;}) : []);
        var nm = 0;
        
        for (var i = 1; i < pathPoints.length; i++){
          var a = pathPoints[i-1], b = pathPoints[i];
          var R = 6371e3; // Earth radius in meters
          var toRad = function(d){ return d * Math.PI / 180; };
          var dLat = toRad(b[0] - a[0]);
          var dLon = toRad(b[1] - a[1]);
          var lat1 = toRad(a[0]);
          var lat2 = toRad(b[0]);
          var sinDLat = Math.sin(dLat / 2);
          var sinDLon = Math.sin(dLon / 2);
          var h = sinDLat * sinDLat + Math.cos(lat1) * Math.cos(lat2) * sinDLon * sinDLon;
          var d = 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
          nm += d / 1852; // meters to nautical miles
        }
        
        // Add distance box
        if (nm > 0){
          var box = L.control({ position: 'bottomright' });
          box.onAdd = function(){
            var div = L.DomUtil.create('div', 'ssyc-map-box');
            div.innerHTML = '<div class="ssyc-map-box-h">Total Distance</div><div class="ssyc-map-box-v">' + Math.round(nm) + ' NM</div>';
            return div;
          };
          box.addTo(map);
        }
        
      } catch (err) {
        console.error('[SSYC] Map initialization error:', err);
      }
    });
  }
  
  // Initialize maps on DOM ready
  if (document.readyState !== 'loading') {
    initSSYCMaps();
  } else {
    document.addEventListener('DOMContentLoaded', initSSYCMaps);
  }
  
  // Fallback: retry after a delay (handles delayed Leaflet loading)
  setTimeout(initSSYCMaps, 1200);
  
  /* ========================================
   * Smooth Scroll to Anchors
   * ======================================== */
  document.addEventListener('click', function(e){
    var link = e.target.closest('a[href^="#"]');
    if (!link) return;
    
    var href = link.getAttribute('href');
    if (href === '#') return;
    
    var target = document.querySelector(href);
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
  
})();

