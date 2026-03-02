<?php
/**
 * Admin Features for Yacht Charters
 * Custom columns, filters, and metabox configurations
 */

if ( ! defined('ABSPATH') ) exit;

/* ========================================
 * Custom Admin Columns
 * ======================================== */
add_filter('manage_edit-yacht_charter_columns', function($cols){
  $new_cols = [];
  $new_cols['cb'] = $cols['cb'];
  $new_cols['title'] = $cols['title'];
  $new_cols['location'] = __('Location', 'sailscanner');
  $new_cols['region'] = __('Region', 'sailscanner');
  $new_cols['featured'] = __('Featured', 'sailscanner');
  $new_cols['date'] = $cols['date'];
  return $new_cols;
});

add_action('manage_yacht_charter_posts_custom_column', function($col, $post_id){
  if ($col === 'location'){
    $location = get_post_meta($post_id, 'charter_location_name', true);
    echo $location ? esc_html($location) : '—';
  }
  elseif ($col === 'region'){
    $terms = wp_get_post_terms($post_id, 'product_cat', ['fields' => 'names']);
    if (!is_wp_error($terms) && !empty($terms)) {
      echo esc_html(implode(', ', array_slice($terms, 0, 2)));
    } else {
      echo '—';
    }
  }
  elseif ($col === 'featured'){
    $featured = get_post_meta($post_id, 'featured_itinerary', true);
    echo $featured ? '✓' : '—';
  }
}, 10, 2);

/* ========================================
 * Admin Filters
 * ======================================== */
add_action('restrict_manage_posts', function(){
  global $typenow;
  if ($typenow !== 'yacht_charter') return;
  
  // Filter by Region (product_cat taxonomy)
  $taxonomy = 'product_cat';
  $selected = isset($_GET[$taxonomy]) ? sanitize_text_field($_GET[$taxonomy]) : '';
  
  $info = get_taxonomy($taxonomy);
  wp_dropdown_categories([
    'show_option_all' => sprintf(__('All %s', 'sailscanner'), $info->label),
    'taxonomy'        => $taxonomy,
    'name'            => $taxonomy,
    'orderby'         => 'name',
    'selected'        => $selected,
    'hierarchical'    => true,
    'show_count'      => true,
    'hide_empty'      => true,
    'value_field'     => 'slug',
  ]);
});

add_filter('parse_query', function($query){
  global $pagenow, $typenow;
  
  if ($pagenow === 'edit.php' && $typenow === 'yacht_charter' && isset($_GET['product_cat']) && $_GET['product_cat'] !== '') {
    $query->query_vars['product_cat'] = sanitize_text_field($_GET['product_cat']);
  }
});

/* ========================================
 * Make columns sortable
 * ======================================== */
add_filter('manage_edit-yacht_charter_sortable_columns', function($cols){
  $cols['location'] = 'charter_location_name';
  return $cols;
});

add_action('pre_get_posts', function($query){
  if (!is_admin() || !$query->is_main_query()) return;
  
  $orderby = $query->get('orderby');
  
  if ($orderby === 'charter_location_name') {
    $query->set('meta_key', 'charter_location_name');
    $query->set('orderby', 'meta_value');
  }
});

/* ========================================
 * Admin notices / help text
 * ======================================== */
add_action('admin_notices', function(){
  $screen = get_current_screen();
  if ($screen && $screen->post_type === 'yacht_charter' && $screen->base === 'post') {
    echo '<div class="notice notice-info is-dismissible">';
    echo '<p><strong>Yacht Charter Tips:</strong> Use shortcodes like <code>[ssyc_map]</code>, <code>[ssyc_weather]</code>, <code>[ssyc_highlights]</code> in your content blocks or Kadence blocks.</p>';
    echo '</div>';
  }
});

