<?php
/**
 * Inline CSS for Yacht Charters
 * Responsive, mobile-first styling matching SailScanner design system
 */

if ( ! defined('ABSPATH') ) exit;

$css = "
/* ========================================
 * Buttons
 * ======================================== */
.ssyc-btn{
  display:inline-block;
  padding:12px 24px;
  border-radius:999px;
  font-weight:700;
  text-decoration:none;
  transition:all .2s ease;
  cursor:pointer;
  border:2px solid transparent;
}
.ssyc-btn-primary{
  background:var(--global-palette1, #0ea5e9);
  color:#fff;
}
.ssyc-btn-primary:hover{
  background:var(--global-palette2, #0284c7);
  color:#fff;
}
.ssyc-btn-secondary{
  background:#fff;
  color:var(--global-palette1, #0ea5e9);
  border-color:#fff;
}
.ssyc-btn-secondary:hover{
  background:transparent;
  color:#fff;
  border-color:#fff;
}
.ssyc-btn-large{
  padding:16px 32px;
  font-size:1.1rem;
}

/* ========================================
 * USPs / Value Props
 * ======================================== */
.ssyc-usps{
  display:grid;
  grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));
  gap:2rem;
  margin:3rem 0;
}
.ssyc-usp{
  text-align:center;
  padding:1.5rem;
  background:#f8fafc;
  border-radius:12px;
  box-shadow: 0px 0px 30px 3px rgba(0, 0, 0, 0.17);
  transition: 0.3s;
}
.ssyc-usp:hover{
  transform: translateY(-3px);
  box-shadow: 0px 0px 14px 0px rgba(0, 0, 0, 0.2);
}
.ssyc-usp-icon{
  margin-bottom:1rem;
}
.ssyc-usp-title{
  font-size:1.1rem;
  font-weight:700;
  margin:0 0 .5rem;
}
.ssyc-usp-caption{
  font-size:.95rem;
  opacity:.8;
  margin:0;
}

/* ========================================
 * Intro & Content Blocks
 * ======================================== */
.ssyc-intro{
  max-width:900px;
  margin:2rem auto;
  font-size:1.05rem;
  line-height:1.7;
}

/* ========================================
 * Highlights / Cards Grid
 * ======================================== */
.ssyc-highlights{
  display:grid;
  grid-template-columns:repeat(auto-fill, minmax(280px, 1fr));
  gap:1.5rem;
  margin:3rem 0;
}
/* Desktop-only override: 3-up */
@media (min-width: 901px) {
  .ssyc-highlights {
    grid-template-columns: repeat(3, 1fr);
  }
}
.ssyc-highlight-card{
  background:#fff;
  border:1px solid rgba(0,0,0,.08);
  border-radius:14px;
  overflow:hidden;
  box-shadow:0 4px 12px rgba(0,0,0,.06);
  transition:transform .2s ease, box-shadow .2s ease;
}
.ssyc-highlight-card:hover{
  transform:translateY(-4px);
  box-shadow:0 8px 24px rgba(0,0,0,.12);
}
.ssyc-highlight-image{
  width:100%;
  height:180px;
  background-size:cover;
  background-position:center;
}
.ssyc-highlight-body{
  padding:1.25rem;
}
.ssyc-highlight-title{
  font-size:1.15rem;
  font-weight:700;
  margin:0 0 .5rem;
}
.ssyc-highlight-summary{
  font-size:.95rem;
  line-height:1.6;
  margin:0;
  opacity:.85;
}

/* ========================================
 * Featured Itinerary
 * ======================================== */
.ssyc-featured-itinerary{
  display:grid;
  grid-template-columns:1fr;
  gap:2rem;
  background:#fff;
  border:1px solid rgba(0,0,0,.08);
  border-radius:14px;
  overflow:hidden;
  box-shadow:0 6px 18px rgba(0,0,0,.08);
  margin:3rem 0;
}
@media(min-width:700px){
  .ssyc-featured-itinerary{
    grid-template-columns:400px 1fr;
  }
}
.ssyc-featured-image{
  width:100%;
  height:300px;
  background-size:cover;
  background-position:center;
}
@media(min-width:700px){
  .ssyc-featured-image{height:100%;min-height:300px}
}
.ssyc-featured-body{
  padding:2rem;
}
.ssyc-featured-title{
  font-size:1.75rem;
  font-weight:800;
  margin:0 0 1rem;
}
.ssyc-featured-summary{
  font-size:1.05rem;
  line-height:1.7;
  margin:0 0 1.5rem;
  opacity:.9;
}

/* ========================================
 * Charter Types
 * ======================================== */
.ssyc-charter-types{
  display:grid;
  grid-template-columns:repeat(auto-fill, minmax(250px, 1fr));
  gap:1.5rem;
  margin:3rem 0;
}
.ssyc-charter-type{
  background:#ffffff;
  border-radius:12px;
  padding:1.5rem;
  box-shadow: 0px 0px 30px 3px rgba(0, 0, 0, 0.17);
  transition: 0.3s;
}
.ssyc-charter-type:hover{
  transform: translateY(-3px);
  box-shadow: 0px 0px 14px 0px rgba(0, 0, 0, 0.2);
}
.ssyc-type-title{
  font-size:1.25rem;
  font-weight:700;
  margin:0 0 1rem;
  color:#12305c;
}
.ssyc-benefits{
  list-style:none;
  padding:0;
  padding-left:0!important;
  margin:0;
}
.ssyc-benefits li{
  padding:.5rem 0;
  padding-left:1.5rem;
  position:relative;
}
.ssyc-benefits li:before{
  content:'✓';
  position:absolute;
  left:0;
  color:#0ea5e9;
  font-weight:700;
}

/* ========================================
 * Map
 * ======================================== */
.ssyc-map{
  margin:3rem 0;
  border-radius:12px;
  overflow:hidden;
}
.ssyc-map-geojson{
  width:100%;
  height:520px;
  background:#eef1f5;
}

/* ========================================
 * Weather
 * ======================================== */
.ssyc-wx-wrap{
  text-align:center;
  margin:2rem 0;
  color:#ffffff;
}
.ssyc-wx-label{
  display:block;
  font-size:.9rem;
  opacity:.8;
  margin-bottom:.5rem;
}
.ssyc-chip{
  display:inline-block;
  background:#12305ccc;
  color:#fff;
  border-radius:999px;
  padding:8px 16px;
  font-weight:700;
  font-size:.95rem;
}
.ssyc-chip-wx{
  background:#091d3acc;
}
.ssyc-wx-live{
  display:block;
  font-size:.85rem;
  opacity:.75;
  margin-top:.5rem;
}
.ssyc-live-dot{
  display:inline-block;
  width:7px;
  height:7px;
  border-radius:999px;
  background:#ef4444;
  margin-right:6px;
  animation:ssyc-pulse 5s ease-in-out infinite;
}
@keyframes ssyc-pulse{
  0%{opacity:.25}
  50%{opacity:1}
  100%{opacity:.25}
}

/* ========================================
 * Pricing Table
 * ======================================== */
.ssyc-pricing{
  margin:3rem 0;
}
.ssyc-pricing-table{
  width:100%;
  border-collapse:collapse;
  background:#fff;
  border-radius:12px;
  overflow:hidden;
  box-shadow:0 4px 12px rgba(0,0,0,.06);
  margin-bottom: 0.5rem!important;

}
.ssyc-pricing-table thead{
  background:#12305c;
  color:#fff;
}
.ssyc-pricing-table th,
.ssyc-pricing-table td{
  padding:1rem;
  text-align:left;
}
.ssyc-pricing-table tbody tr{
  border-bottom:1px solid rgba(0,0,0,.06);
}
.ssyc-pricing-table tbody tr:last-child{
  border-bottom:none;
}
.ssyc-pricing-notes{
  margin-top:none;
  padding:0 1rem;
  background:#f8fafc;
  border-radius:12px;
  font-size:.85rem;
  line-height:1.6;
  color: #908f8f;
}

/* ========================================
 * Process Steps
 * ======================================== */
.ssyc-process{
  display:grid;
  grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));
  gap:2rem;
  margin:3rem 0;
}
.ssyc-process-step{
  text-align:center;
  padding:1.5rem;
  background:#fff;
  border:1px solid rgba(0,0,0,.06);
  border-radius:12px;
  position:relative;
  box-shadow: 0px 0px 30px 3px rgba(0, 0, 0, 0.17);
  transition: 0.3s;
}
.ssyc-process-step:hover{
  transform: translateY(-3px);
  box-shadow: 0px 0px 14px 0px rgba(0, 0, 0, 0.2);
}
.ssyc-step-number{
  position:absolute;
  top:-12px;
  left:50%;
  transform:translateX(-50%);
  width:32px;
  height:32px;
  border-radius:999px;
  background:#0ea5e9;
  color:#fff;
  font-weight:700;
  display:grid;
  place-items:center;
  font-size:.9rem;
}
.ssyc-step-icon{
  margin:1rem 0;
}
.ssyc-step-title{
  font-size:1.1rem;
  font-weight:700;
  margin:.5rem 0;
}
.ssyc-step-summary{
  font-size:.95rem;
  line-height:1.6;
  opacity:.85;
  margin:0;
}

/* ========================================
 * Why Us / Trust Badges
 * ======================================== */
.ssyc-why-us{
  margin:3rem 0;
  padding:2rem;
  background:#f8fafc;
  border-radius:14px;
}
.ssyc-trust-badges{
  display:flex;
  gap:1.5rem;
  justify-content:center;
  flex-wrap:wrap;
  margin-top:2rem;
}
.ssyc-badge{
  height:60px;
  width:auto;
  filter:grayscale(50%);
  transition:filter .2s ease;
}
.ssyc-badge:hover{
  filter:grayscale(0);
}

/* ========================================
 * Reviews / Trustpilot
 * ======================================== */
.ssyc-reviews{
  margin:3rem 0;
}
.ssyc-tp-banner{
  text-align:center;
  padding:3rem 2rem;
  background:#fff;
  border:1px solid rgba(0,0,0,.06);
  border-radius:14px;
  box-shadow:0 6px 18px rgba(0,0,0,.08);
}
.ssyc-tp-stars{
  margin-bottom:1rem;
}
.ssyc-stars{
  position:relative;
  display:inline-block;
  line-height:0;
}
.ssyc-stars svg{
  width:24px;
  height:24px;
  display:inline-block;
  vertical-align:middle;
}
.ssyc-stars svg+svg{
  margin-left:4px;
}
.ssyc-stars-bg,.ssyc-stars-fill{
  display:inline-block;
  white-space:nowrap;
}
.ssyc-stars-fill{
  position:absolute;
  left:0;
  top:0;
  height:100%;
  overflow:hidden;
  pointer-events:none;
}
.ssyc-tp-headline{
  font-size:1.5rem;
  font-weight:700;
  margin:.5rem 0;
}
.ssyc-tp-caption{
  font-size:1rem;
  opacity:.8;
  margin:0 0 1.5rem;
}

/* ========================================
 * FAQs
 * ======================================== */
.ssyc-faqs{
  margin:3rem 0;
}
.ssyc-faq-item{
  border:1px solid rgba(0,0,0,.06);
  border-radius:12px;
  margin-bottom:1rem;
  overflow:hidden;
  background:#fff;
  transition: 0.3s;
}
.ssyc-faq-toggle{
  display:flex;
  justify-content:space-between;
  align-items:center;
  width:100%;
  padding:1.25rem 1.5rem;
  background:#ffffff!important;
  border:none;
  cursor:pointer;
  text-align:left;
  font-size:1rem;
  font-weight:700;
  color:#12305c;
  transition: 0.3s;
}
.ssyc-faq-toggle:hover{
  color:#12305c;
  transition: 0.3s;
}
.ssyc-faq-toggle:focus{
  outline:none;
  transition: 0.3s;
}
.ssyc-faq-toggle[aria-expanded=\"true\"]{
  color:#12305c;
}
.ssyc-faq-question{
  color:#12305c;
  transition: 0.3s;
}
.ssyc-faq-icon{
  transition:transform .2s ease;
  display:inline-flex;
}
.ssyc-faq-toggle[aria-expanded=\"true\"] .ssyc-faq-icon{
  transform:rotate(180deg);
}
.ssyc-faq-answer{
  padding:1.5rem;
  line-height:1.7;
  color:#334155;
  transition: 0.3s;
}

/* ========================================
 * Related Content Grid
 * ======================================== */
.ssyc-related-guides,
.ssyc-related-itineraries{
  margin:3rem 0;
}
.ssyc-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill, minmax(280px, 1fr));
  gap:1.5rem;
  margin-top:1.5rem;
}
.ssyc-card{
  background:#fff;
  border:1px solid rgba(0,0,0,.08);
  border-radius:14px;
  overflow:hidden;
  box-shadow:0 4px 12px rgba(0,0,0,.06);
  transition:transform .2s ease, box-shadow .2s ease;
}
.ssyc-card:hover{
  transform:translateY(-4px);
  box-shadow:0 8px 24px rgba(0,0,0,.12);
}
.ssyc-card-image{
  width:100%;
  height:180px;
  background-size:cover;
  background-position:center;
}
.ssyc-card-body{
  padding:1.25rem;
}
.ssyc-card-title{
  font-size:1.1rem;
  font-weight:700;
  margin:0 0 .5rem;
}
.ssyc-card-title a{
  color:inherit;
  text-decoration:none;
}
.ssyc-card-title a:hover{
  color:#0ea5e9;
}
.ssyc-card-excerpt,
.ssyc-card-subtitle{
  font-size:.95rem;
  line-height:1.6;
  margin:0;
  opacity:.85;
}

/* ========================================
 * Footer CTA
 * ======================================== */
.ssyc-footer-cta{
  text-align:center;
  padding:4rem 2rem;
  background:linear-gradient(135deg, #12305c 0%, #0ea5e9 100%);
  color:#fff;
  border-radius:14px;
  margin:3rem 0;
}
.ssyc-footer-cta-heading{
  font-size:2rem;
  font-weight:800;
  margin:0 0 1rem;
}
.ssyc-footer-cta-subtext{
  font-size:1.15rem;
  margin:0 0 2rem;
  opacity:.95;
}

/* ========================================
 * Form Wrapper
 * ======================================== */
.ssyc-form-wrap{
  margin:3rem 0;
}
.ssyc-form-pos-sidebar_desktop{
  /* Can be styled as sticky sidebar with custom CSS */
}

/* ========================================
 * Mobile Responsiveness
 * ======================================== */
@media(max-width:700px){
  .ssyc-usps{grid-template-columns:1fr}
  .ssyc-highlights{grid-template-columns:1fr}
  .ssyc-charter-types{grid-template-columns:1fr}
  .ssyc-process{grid-template-columns:1fr}
  .ssyc-grid{grid-template-columns:1fr}
  .ssyc-pricing-table{font-size:.9rem}
  .ssyc-pricing-table th,
  .ssyc-pricing-table td{padding:.75rem .5rem}
  .ssyc-footer-cta{padding:3rem 1.5rem}
  .ssyc-footer-cta-heading{font-size:1.5rem}
}

/* ========================================
 * Leaflet Map Customization
 * Using itineraries map classes (.ssi-pt from ssi-v3.js)
 * ======================================== */
.ssi-pt .ssi-pt-i,
.ssyc-pt .ssyc-pt-i{
  width:26px;
  height:26px;
  border-radius:999px;
  background:#3b82f6;
  color:#fff;
  display:grid;
  place-items:center;
  font-weight:800;
  box-shadow:0 1px 2px rgba(0,0,0,0.25);
}
.ssi-map-box,
.ssyc-map-box{
  background:rgba(255,255,255,0.95);
  padding:8px 12px;
  border-radius:6px;
  box-shadow:0 2px 8px rgba(0,0,0,0.15);
}
.ssi-map-box-h,
.ssyc-map-box-h{
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:0.5px;
  opacity:0.7;
  margin-bottom:2px;
}
.ssi-map-box-v,
.ssyc-map-box-v{
  font-size:18px;
  font-weight:800;
  color:#3b82f6;
}
.leaflet-tooltip{
  background:#12305c;
  color:#fff;
  border:0;
  border-radius:8px;
  padding:6px 8px;
  font-weight:700;
}
";

wp_add_inline_style('ssyc-style', $css);


