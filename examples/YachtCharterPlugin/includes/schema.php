<?php
/**
 * JSON-LD Schema Markup for Yacht Charters
 * FAQPage, BreadcrumbList, TouristTrip, Place schemas
 */

if ( ! defined('ABSPATH') ) exit;

/* ========================================
 * Main Schema Output
 * ======================================== */
add_action('wp_head', function(){
  if (!is_singular('yacht_charter')) return;
  
  $post_id = get_the_ID();
  $graph = ['@context' => 'https://schema.org', '@graph' => []];
  
  // 1. BreadcrumbList
  $breadcrumb = ssyc_generate_breadcrumb_schema($post_id);
  if ($breadcrumb) $graph['@graph'][] = $breadcrumb;
  
  // 2. TouristTrip / Place
  $trip = ssyc_generate_trip_schema($post_id);
  if ($trip) $graph['@graph'][] = $trip;
  
  // 3. FAQPage
  $faq = ssyc_generate_faq_schema($post_id);
  if ($faq) $graph['@graph'][] = $faq;
  
  if (!empty($graph['@graph'])) {
    echo '<script type="application/ld+json" class="ssyc-schema">'.
      wp_json_encode($graph, JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE).
      '</script>';
  }
}, 20);

/* ========================================
 * Breadcrumb Schema
 * ======================================== */
function ssyc_generate_breadcrumb_schema($post_id){
  $permalink = get_permalink($post_id);
  $archive_url = get_post_type_archive_link('yacht_charter');
  if (!$archive_url) $archive_url = home_url('/yacht-charters/');
  
  return [
    '@type' => 'BreadcrumbList',
    '@id' => trailingslashit($permalink) . '#breadcrumb',
    'itemListElement' => [
      [
        '@type' => 'ListItem',
        'position' => 1,
        'item' => [
          '@id' => home_url('/'),
          'name' => 'Home',
        ],
      ],
      [
        '@type' => 'ListItem',
        'position' => 2,
        'item' => [
          '@id' => $archive_url,
          'name' => 'Yacht Charters',
        ],
      ],
      [
        '@type' => 'ListItem',
        'position' => 3,
        'item' => [
          '@id' => $permalink,
          'name' => get_the_title($post_id),
        ],
      ],
    ],
  ];
}

/* ========================================
 * TouristTrip / Place Schema
 * ======================================== */
function ssyc_generate_trip_schema($post_id){
  $name = get_the_title($post_id);
  $location_name = function_exists('get_field') ? get_field('charter_location_name', $post_id) : get_post_meta($post_id, 'charter_location_name', true);
  $desc = get_the_excerpt($post_id);
  // Fallback to intro_html (ACF) if no excerpt
  if (!$desc && function_exists('get_field')) {
    $intro_html = get_field('intro_html', $post_id);
    if ($intro_html) $desc = wp_strip_all_tags($intro_html);
  }
  $url = get_permalink($post_id);
  $img = get_the_post_thumbnail_url($post_id, 'large');
  
  // Prefer ACF for geo (falls back to post meta)
  $lat = function_exists('get_field') ? get_field('geo_lat', $post_id) : get_post_meta($post_id, 'geo_lat', true);
  $lon = function_exists('get_field') ? get_field('geo_lon', $post_id) : get_post_meta($post_id, 'geo_lon', true);
  
  $trip = [
    '@type' => ['TouristTrip', 'Place'],
    'name' => $name,
    'url' => $url,
  ];
  
  if ($desc) $trip['description'] = wp_strip_all_tags($desc);
  if ($img) $trip['image'] = [$img];
  
  if ($lat && $lon) {
    $trip['geo'] = [
      '@type' => 'GeoCoordinates',
      'latitude' => (float)$lat,
      'longitude' => (float)$lon,
    ];
  }
  
  if ($location_name) {
    $trip['address'] = [
      '@type' => 'PostalAddress',
      'addressLocality' => $location_name,
    ];
  }
  
  // Pricing offer
  $currency = function_exists('get_field') ? get_field('currency_code', $post_id) : get_post_meta($post_id, 'currency_code', true);
  if (!$currency) $currency = 'EUR';
  
  // Use ACF repeater when available (more reliable than raw post meta)
  $pricing_rows = function_exists('get_field') ? get_field('pricing_table', $post_id) : get_post_meta($post_id, 'pricing_table', true);
  if ($pricing_rows && is_array($pricing_rows)) {
    $min_price = PHP_INT_MAX;
    $max_price = 0;
    
    foreach ($pricing_rows as $row) {
      foreach (['bareboat_from','catamaran_from','crewed_from'] as $k) {
        if (isset($row[$k]) && $row[$k] > 0) {
          $min_price = min($min_price, $row[$k]);
          $max_price = max($max_price, $row[$k]);
        }
      }
    }
    
    if ($min_price < PHP_INT_MAX && $max_price > 0) {
      $trip['offers'] = [
        '@type' => 'AggregateOffer',
        'priceCurrency' => $currency,
        'lowPrice' => (string)$min_price,
        'highPrice' => (string)$max_price,
        'url' => $url,
        'availability' => 'https://schema.org/InStock',
      ];
    }
  }
  
  return $trip;
}

/* ========================================
 * FAQ Schema
 * ======================================== */
function ssyc_generate_faq_schema($post_id){
  // Prefer ACF (repeater + toggle), fallback to raw post meta if ACF unavailable
  $enable_schema = function_exists('get_field')
    ? get_field('faqs_enable_schema', $post_id)
    : get_post_meta($post_id, 'faqs_enable_schema', true);
  if (!$enable_schema) return null;
  
  $faqs = function_exists('get_field')
    ? get_field('faqs', $post_id)
    : get_post_meta($post_id, 'faqs', true);
  if (!$faqs || !is_array($faqs) || empty($faqs)) return null;
  
  $entities = [];
  foreach ($faqs as $faq) {
    $q = is_array($faq) && isset($faq['faq_question']) ? $faq['faq_question'] : '';
    $a = is_array($faq) && isset($faq['faq_answer'])   ? $faq['faq_answer']   : '';
    if (!$q || !$a) continue;
    
    $entities[] = [
      '@type' => 'Question',
      'name' => $q,
      'acceptedAnswer' => [
        '@type' => 'Answer',
        'text' => wp_strip_all_tags($a),
      ],
    ];
  }
  
  if (empty($entities)) return null;
  
  return [
    '@type' => 'FAQPage',
    'mainEntity' => $entities,
  ];
}

/* ========================================
 * Disable Rank Math JSON-LD on Yacht Charters
 * (to avoid duplicate schema)
 * ======================================== */
add_filter('rank_math/json_ld', function($data, $jsonld){
  if (is_singular('yacht_charter')) {
    // Keep only breadcrumb from Rank Math if desired, or remove all
    return [];
  }
  return $data;
}, 99, 2);

/* ========================================
 * Fix <html itemtype> for Yacht Charters
 * ======================================== */
add_filter('language_attributes', function($attrs){
  if (!is_singular('yacht_charter')) return $attrs;
  
  // Remove any existing itemscope/itemtype
  $attrs = preg_replace('/\sitemscope(="")?/i', '', $attrs);
  $attrs = preg_replace('/\sitemtype="[^"]*"/i', '', $attrs);
  
  // Add WebPage type
  $attrs .= ' itemscope itemtype="https://schema.org/WebPage"';
  return $attrs;
}, 20);

