<?php
/**
 * SailScanner – Yacht Charters
 * 
 * Can be loaded as MU Plugin via: /wp-content/mu-plugins/yacht-charter-loader.php
 * Or as regular plugin from: /wp-content/plugins/YachtCharterPlugin/
 * 
 * Description: Yacht Charter CPT with ACF fields, shortcodes for Kadence, weather integration, and Leaflet maps
 * Version:     1.0.0
 * Author:      SailScanner
 * Text Domain: sailscanner
 */

if ( ! defined('ABSPATH') ) exit;

define('SSYC_VER', '1.0.0');
define('SSYC_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('SSYC_PLUGIN_URL', plugin_dir_url(__FILE__));

/* ---------------------------------------------------------
 * ACF Dependency Check
 * MU plugins load before regular plugins, so we need to 
 * ensure ACF is available before registering field groups
 * -------------------------------------------------------*/
add_action('plugins_loaded', function(){
  // Check if ACF is available
  if ( ! function_exists('acf_add_local_field_group') ) {
    // Show admin notice if ACF is missing
    add_action('admin_notices', function(){
      echo '<div class="error"><p><strong>SailScanner Yacht Charters:</strong> This plugin requires Advanced Custom Fields Pro. Please install and activate ACF Pro.</p></div>';
    });
    return; // Stop loading if ACF is not available
  }
}, 5); // Priority 5 to run early but after most plugins

/* ---------------------------------------------------------
 * 1) Register CPT and attach WooCommerce taxonomy
 * -------------------------------------------------------*/
add_action('init', function(){
  register_post_type('yacht_charter', [
    'labels' => [
      'name'               => __('Yacht Charters', 'sailscanner'),
      'singular_name'      => __('Yacht Charter', 'sailscanner'),
      'menu_name'          => __('Yacht Charters', 'sailscanner'),
      'add_new'            => __('Add New', 'sailscanner'),
      'add_new_item'       => __('Add New Yacht Charter', 'sailscanner'),
      'edit_item'          => __('Edit Yacht Charter', 'sailscanner'),
      'new_item'           => __('New Yacht Charter', 'sailscanner'),
      'view_item'          => __('View Yacht Charter', 'sailscanner'),
      'search_items'       => __('Search Yacht Charters', 'sailscanner'),
      'not_found'          => __('No yacht charters found', 'sailscanner'),
      'not_found_in_trash' => __('No yacht charters found in Trash', 'sailscanner'),
      'all_items'          => __('All Yacht Charters', 'sailscanner'),
    ],
    'public'               => true,
    'publicly_queryable'   => true,
    'show_ui'              => true,
    'show_in_menu'         => true,
    'show_in_nav_menus'    => true,
    'show_in_admin_bar'    => true,
    'show_in_rest'         => true,
    'has_archive'          => true,
    'exclude_from_search'  => false,
    'rewrite'              => [
      'slug'       => 'yacht-charters',
      'with_front' => false,
      'feeds'      => true,
      'pages'      => true,
    ],
    'rest_base'            => 'yacht-charters',
    'menu_icon'            => 'dashicons-palmtree',
    'menu_position'        => 20,
    'supports'             => ['title', 'editor', 'thumbnail', 'excerpt', 'revisions'],
    'taxonomies'           => ['product_cat'],
    'capability_type'      => 'post',
    'map_meta_cap'         => true,
    'hierarchical'         => false,
    'can_export'           => true,
  ]);

  // Ensure WooCommerce product_cat is registered to yacht_charter and destinations
  if ( taxonomy_exists('product_cat') ) {
    register_taxonomy_for_object_type('product_cat', 'yacht_charter');
    // Note: destinations CPT should already have product_cat registered by its own plugin
  }
}, 5);

// Ensure product_cat is registered after all plugins load
add_action('init', function(){
  if ( taxonomy_exists('product_cat') ) {
    register_taxonomy_for_object_type('product_cat', 'yacht_charter');
  }
}, 20);

/* ---------------------------------------------------------
 * 2) Helper Functions
 * -------------------------------------------------------*/
if ( ! function_exists('ssyc_get') ) {
  function ssyc_get($key, $post_id = null){
    $pid = $post_id ?: get_the_ID();
    
    // PREVIEW FIX: Handle WordPress preview mode correctly
    // When previewing, get_the_ID() might return wrong ID or revision ID
    if (!$post_id && is_preview()) {
      global $wp_query;
      if (isset($wp_query->post)) {
        $pid = $wp_query->post->ID;
      }
      // Also check for preview query var
      if (isset($_GET['preview_id'])) {
        $pid = intval($_GET['preview_id']);
      } elseif (isset($_GET['p'])) {
        $pid = intval($_GET['p']);
      }
    }
    
    if ( function_exists('get_field') ) {
      // CRITICAL FIX: Explicitly ensure ACF field groups are loaded
      // In Kadence Elements, field registry may not be populated even after acf/init
      // We need to force-load the field groups for this post type
      static $fields_loaded = false;
      if (!$fields_loaded && function_exists('acf_get_field_groups')) {
        $groups = acf_get_field_groups(['post_type' => 'yacht_charter']);
        foreach ($groups as $group) {
          acf_get_fields($group);
        }
        $fields_loaded = true;
      }
      
      // In preview mode, ACF might need format parameter set to false
      $value = get_field($key, $pid, false);
      
      // If still empty in preview, try getting from the actual post (not revision)
      if (empty($value) && is_preview() && $pid) {
        $parent_id = wp_is_post_revision($pid);
        if ($parent_id) {
          $value = get_field($key, $parent_id, false);
        }
      }
      
      return $value;
    }
    
    return get_post_meta($pid, $key, true);
  }
}

if ( ! function_exists('ssyc_deg_to_cardinal') ){
  function ssyc_deg_to_cardinal($deg){
    $dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
    $ix = floor((($deg + 11.25) % 360) / 22.5);
    return $dirs[$ix];
  }
}

if ( ! function_exists('ssyc_svg') ){
  function ssyc_svg($name, $color = '#12305c', $size = 18){
    if (!$name) return '';
    
    // Support for custom shorthand names (backwards compatibility)
    $mat = [
      'calendar'=>'calendar_month', 'weather'=>'air', 'pointer'=>'near_me',
      'pin'=>'location_on', 'route'=>'conversion_path', 'sailing'=>'sailing',
      'season'=>'early_on', 'price'=>'sell', 'anchor'=>'anchor',
      'water'=>'kayaking', 'wrench'=>'hiking', 'restaurant'=>'flatware',
      'sight'=>'local_see', 'services'=>'electrical_services', 'warning'=>'warning',
      'tips'=>'assignment_globe', 'drone'=>'drone', 'gauge'=>'sailing',
      'ruler'=>'near_me', 'time'=>'sailing', 'star'=>'star', 'check'=>'check_circle'
    ];
    
    // Use mapped name if exists, otherwise use the name directly as Material icon ligature
    $lig = isset($mat[$name]) ? $mat[$name] : $name;
    
    // Clean up ligature (remove extra spaces, handle multiple words)
    $lig = trim(preg_replace('/\s+/', '_', $lig));
    
    $style = 'font-variation-settings:\'"opsz"\' 24, \'"wght"\' 300, \'"FILL"\' 0, \'"GRAD"\' 200; font-size:'.(int)$size.'px; color:'.esc_attr($color).'; line-height:1; display:inline-block; vertical-align:middle;';
    return '<span class="material-symbols-sharp ms-ico" aria-hidden="true" style="'.$style.'">'.esc_html($lig).'</span>';
  }
}

if ( ! function_exists('ssyc_render_stars') ){
  function ssyc_render_stars($rating){
    $r = max(0, min(5, floatval($rating)));
    $pct = (string)($r * 20).'%';
    $star = ssyc_svg('star', '#d1d5db', 16);
    $star_fill = ssyc_svg('star', '#fbbf24', 16);
    $bg = str_repeat($star, 5);
    $fg = str_repeat($star_fill, 5);
    return '<span class="ssyc-stars"><span class="ssyc-stars-bg">'.$bg.'</span><span class="ssyc-stars-fill" style="width:'.$pct.'">'.$fg.'</span></span>';
  }
}

/* ---------------------------------------------------------
 * 3) Weather (Open-Meteo)
 * -------------------------------------------------------*/
if ( ! function_exists('ssyc_fetch_weather') ){
  function ssyc_fetch_weather($post_id){
    $lat = ssyc_get('weather_lat', $post_id);
    $lon = ssyc_get('weather_lon', $post_id);
    
    // Fallback to page meta
    if (!$lat || !$lon) {
      $lat = ssyc_get('geo_lat', $post_id);
      $lon = ssyc_get('geo_lon', $post_id);
    }
    
    if (!$lat || !$lon) return '';
    
    $lat = floatval($lat);
    $lon = floatval($lon);
    $transient_key = 'ssyc_wx_' . md5($lat.','.$lon);
    $data = get_transient($transient_key);
    
    if (!$data) {
      $url = add_query_arg([
        'latitude' => $lat,
        'longitude'=> $lon,
        'current'  => 'temperature_2m,wind_speed_10m,wind_direction_10m',
        'windspeed_unit' => 'kmh',
        'timezone' => 'auto'
      ], 'https://api.open-meteo.com/v1/forecast');
      
      $res = wp_remote_get($url, ['timeout'=>8]);
      if ( is_wp_error($res) ) return '';
      $body = wp_remote_retrieve_body($res);
      $json = json_decode($body, true);
      if (!$json || empty($json['current'])) return '';
      
      $data = [
        't'   => isset($json['current']['temperature_2m']) ? $json['current']['temperature_2m'] : null,
        'wkm' => isset($json['current']['wind_speed_10m']) ? $json['current']['wind_speed_10m'] : null,
        'wdir'=> isset($json['current']['wind_direction_10m']) ? $json['current']['wind_direction_10m'] : null,
      ];
      
      $cache_ttl = ssyc_get('weather_cache_ttl_minutes', $post_id);
      $cache_ttl = $cache_ttl ? (int)$cache_ttl : 180;
      set_transient($transient_key, $data, $cache_ttl * MINUTE_IN_SECONDS);
    }
    
    if (!$data) return '';
    $t   = $data['t'];
    $wkm = $data['wkm'];
    $wkn = ($wkm !== null) ? round(floatval($wkm) * 0.539957) : null;
    $dir = ($data['wdir'] !== null) ? ssyc_deg_to_cardinal(floatval($data['wdir'])) : null;
    
    $parts = [];
    if ($t !== null)   $parts[] = round($t) . "°C";
    if ($wkn !== null) $parts[] = $wkn . " kn";
    if ($dir)          $parts[] = $dir;
    if (!$parts) return '';
    
    $location = ssyc_get('charter_location_name', $post_id) ?: get_the_title($post_id);
    
    $chip = '<span class="ssyc-chip ssyc-chip-wx" title="Current weather">'.esc_html(implode(' • ', $parts)).'</span>';
    return '<div class="ssyc-wx-wrap"><small class="ssyc-wx-label">Current Weather in '.esc_html($location).'</small>'.$chip.'<small class="ssyc-wx-live"><span class="ssyc-live-dot"></span>Live Forecast</small></div>';
  }
}

require_once SSYC_PLUGIN_DIR . 'includes/acf-fields.php';
require_once SSYC_PLUGIN_DIR . 'includes/shortcodes.php';
require_once SSYC_PLUGIN_DIR . 'includes/admin.php';
require_once SSYC_PLUGIN_DIR . 'includes/schema.php';

/* ---------------------------------------------------------
 * Register Assets (available but not loaded until needed)
 * -------------------------------------------------------*/
add_action('wp_enqueue_scripts', function(){
  if ( is_admin() ) return;
  
  // Register styles (don't enqueue yet)
  $h = 'ssyc-style';
  if ( ! wp_style_is($h,'registered') ) {
    wp_register_style($h, false, [], SSYC_VER);
  }
  
  // Material Symbols Sharp
  if ( ! wp_style_is('material-symbols-sharp','registered') ) {
    wp_register_style('material-symbols-sharp', 'https://fonts.googleapis.com/css2?family=Material+Symbols+Sharp:FILL@0..1&display=swap', [], null);
  }
  
  // Leaflet for maps
  if ( ! wp_style_is('leaflet','registered') ) {
    wp_register_style('leaflet', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', [], '1.9.4');
  }
  
  if ( ! wp_script_is('leaflet','registered') ) {
    wp_register_script('leaflet', 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', [], '1.9.4', true);
  }
  
  // Custom JS for YachtCharterPlugin (accordion, smooth scroll, maps init)
  $js_handle = 'ssyc';
  $js_path = SSYC_PLUGIN_URL . 'assets/js/ssyc.js';
  if ( ! wp_script_is($js_handle, 'registered') ) {
    // Depend on Leaflet so maps init runs after Leaflet is available
    wp_register_script($js_handle, $js_path, ['leaflet'], SSYC_VER, true);
  }
  
  // Auto-enqueue on yacht_charter singular posts
  if ( is_singular('yacht_charter') ) {
    wp_enqueue_style($h);
    wp_enqueue_style('material-symbols-sharp');
    wp_enqueue_style('leaflet');
    wp_enqueue_script('leaflet');
    wp_enqueue_script($js_handle);
    require_once SSYC_PLUGIN_DIR . 'includes/styles.php';
  }
}, 10);

/* ---------------------------------------------------------
 * Helper: Enqueue assets when shortcodes are used
 * -------------------------------------------------------*/
if ( ! function_exists('ssyc_enqueue_assets') ) {
  function ssyc_enqueue_assets($include_leaflet = false){
    static $already_enqueued = false;
    
    if (!$already_enqueued) {
      wp_enqueue_style('ssyc-style');
      wp_enqueue_style('material-symbols-sharp');
      wp_enqueue_script('ssyc');
      
      // Inline styles
      if (file_exists(SSYC_PLUGIN_DIR . 'includes/styles.php')) {
        require_once SSYC_PLUGIN_DIR . 'includes/styles.php';
      }
      
      $already_enqueued = true;
    }
    
    // Leaflet only loaded when map shortcode is used
    if ($include_leaflet) {
      static $leaflet_enqueued = false;
      if (!$leaflet_enqueued) {
        wp_enqueue_style('leaflet');
        wp_enqueue_script('leaflet');
        $leaflet_enqueued = true;
      }
    }
  }
}

