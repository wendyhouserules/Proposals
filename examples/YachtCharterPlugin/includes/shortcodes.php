<?php
/**
 * Shortcodes for Yacht Charter Pages
 * All shortcodes use [ssyc_*] prefix
 */

if ( ! defined('ABSPATH') ) exit;

/* ========================================
 * [ssyc_usps] - Value Propositions
 * ======================================== */
add_shortcode('ssyc_usps', function($atts){
  ssyc_enqueue_assets();
  $pid = get_the_ID();
  if ( ! function_exists('have_rows') ) return '';
  
  $html = '';
  if ( have_rows('usps', $pid) ) {
    $html .= '<div class="ssyc-usps">';
    while ( have_rows('usps', $pid) ) { the_row();
      $icon = get_sub_field('usp_icon');
      $title = get_sub_field('usp_title');
      $caption = get_sub_field('usp_caption');
      
      $html .= '<div class="ssyc-usp">';
      if ($icon) $html .= '<div class="ssyc-usp-icon">'.ssyc_svg($icon, '#0ea5e9', 32).'</div>';
      $html .= '<h3 class="ssyc-usp-title">'.esc_html($title).'</h3>';
      if ($caption) $html .= '<p class="ssyc-usp-caption">'.esc_html($caption).'</p>';
      $html .= '</div>';
    }
    $html .= '</div>';
    if ( function_exists('reset_rows') ) reset_rows('usps');
  }
  return $html;
});

/* ========================================
 * [ssyc_intro] - SEO Intro Block
 * ======================================== */
add_shortcode('ssyc_intro', function($atts){
  ssyc_enqueue_assets();
  $pid = get_the_ID();
  $intro = ssyc_get('intro_html', $pid);
  
  if (!$intro) return '';
  
  $html = '<div class="ssyc-intro">';
  $html .= wp_kses_post($intro);
  $html .= '</div>';
  return $html;
});

/* ========================================
 * [ssyc_highlights] - Destination Highlights
 * ======================================== */
add_shortcode('ssyc_highlights', function($atts){
  ssyc_enqueue_assets();
  $pid = get_the_ID();
  $source = ssyc_get('highlights_source', $pid) ?: 'manual';
  $show_count = ssyc_get('highlights_show_count', $pid) ?: 4;
  
  $html = '<div class="ssyc-highlights">';
  
  if ($source === 'manual' && function_exists('have_rows') && have_rows('highlights_cards', $pid)) {
    $count = 0;
    while ( have_rows('highlights_cards', $pid) && $count < $show_count ) { the_row();
      $title = get_sub_field('highlight_title');
      $image = get_sub_field('highlight_image');
      $summary = get_sub_field('highlight_summary');
      $anchor = get_sub_field('highlight_anchor_slug');
      
      $img_url = is_array($image) ? $image['url'] : '';
      $html .= '<div class="ssyc-highlight-card">';
      if ($img_url) $html .= '<div class="ssyc-highlight-image" style="background-image:url(\''.esc_url($img_url).'\');"></div>';
      $html .= '<div class="ssyc-highlight-body">';
      $html .= '<h3 class="ssyc-highlight-title">'.esc_html($title).'</h3>';
      if ($summary) $html .= '<p class="ssyc-highlight-summary">'.esc_html($summary).'</p>';
      $html .= '</div></div>';
      $count++;
    }
    if ( function_exists('reset_rows') ) reset_rows('highlights_cards');
  } elseif ($source === 'from_itinerary') {
    $itinerary_id = ssyc_get('highlights_itinerary_ref', $pid);
    if ($itinerary_id && function_exists('have_rows') && have_rows('ssi_days', $itinerary_id)) {
      $count = 0;
      while ( have_rows('ssi_days', $itinerary_id) && $count < $show_count ) { the_row();
        $title = get_sub_field('ssi_day_title');
        $image = get_sub_field('ssi_day_image');
        $summary = get_sub_field('ssi_day_summary_rich');
        
        $html .= '<div class="ssyc-highlight-card">';
        if ($image) $html .= '<div class="ssyc-highlight-image" style="background-image:url(\''.esc_url($image).'\');"></div>';
        $html .= '<div class="ssyc-highlight-body">';
        $html .= '<h3 class="ssyc-highlight-title">'.esc_html($title).'</h3>';
        if ($summary) $html .= '<p class="ssyc-highlight-summary">'.wp_strip_all_tags(substr($summary, 0, 200)).'...</p>';
        $html .= '</div></div>';
        $count++;
      }
      if ( function_exists('reset_rows') ) reset_rows('ssi_days');
    }
  }
  
  $html .= '</div>';
  return $html;
});

/* ========================================
 * [ssyc_featured_itinerary] - Featured Itinerary Card
 * ======================================== */
add_shortcode('ssyc_featured_itinerary', function($atts){
  ssyc_enqueue_assets();
  $pid = get_the_ID();
  $itinerary_id = ssyc_get('featured_itinerary', $pid);
  if (!$itinerary_id) return '';
  
  $custom_title = ssyc_get('featured_custom_title', $pid);
  $summary = ssyc_get('featured_summary', $pid);
  $cta_label = ssyc_get('featured_cta_label', $pid) ?: 'View Day-by-Day';
  
  $title = $custom_title ?: get_the_title($itinerary_id);
  if (!$summary) $summary = get_the_excerpt($itinerary_id);
  
  $thumb = get_the_post_thumbnail_url($itinerary_id, 'large');
  $url = get_permalink($itinerary_id);
  
  $html = '<div id="featured-itinerary" class="ssyc-featured-itinerary">';
  if ($thumb) $html .= '<div class="ssyc-featured-image" style="background-image:url(\''.esc_url($thumb).'\');"></div>';
  $html .= '<div class="ssyc-featured-body">';
  $html .= '<h2 class="ssyc-featured-title">'.esc_html($title).'</h2>';
  if ($summary) $html .= '<p class="ssyc-featured-summary">'.esc_html($summary).'</p>';
  $html .= '<a href="'.esc_url($url).'" class="ssyc-btn ssyc-btn-primary">'.esc_html($cta_label).'</a>';
  $html .= '</div></div>';
  
  return $html;
});

/* ========================================
 * [ssyc_charter_types] - Charter Types Grid
 * ======================================== */
add_shortcode('ssyc_charter_types', function($atts){
  ssyc_enqueue_assets();
  $pid = get_the_ID();
  $types = ssyc_get('charter_types', $pid);
  if (empty($types) || !is_array($types)) return '';
  
  $type_labels = [
    'bareboat' => 'Bareboat',
    'skippered' => 'Skippered',
    'catamaran' => 'Catamaran',
    'crewed_luxury' => 'Crewed Luxury',
    'gulet' => 'Gulet',
    'by_cabin' => 'By Cabin'
  ];
  
  $html = '<div class="ssyc-charter-types">';
  foreach ($types as $type) {
    $label = isset($type_labels[$type]) ? $type_labels[$type] : $type;
    $html .= '<div class="ssyc-charter-type">';
    $html .= '<h3 class="ssyc-type-title">'.esc_html($label).'</h3>';
    
    // Find benefits for this type
    if ( function_exists('have_rows') && have_rows('charter_type_benefits', $pid) ) {
      while ( have_rows('charter_type_benefits', $pid) ) { the_row();
        $type_key = get_sub_field('type_key');
        if ($type_key === $type && have_rows('benefit_points') ) {
          $html .= '<ul class="ssyc-benefits">';
          while ( have_rows('benefit_points') ) { the_row();
            $benefit = get_sub_field('benefit');
            if ($benefit) $html .= '<li>'.esc_html($benefit).'</li>';
          }
          $html .= '</ul>';
        }
      }
      if ( function_exists('reset_rows') ) reset_rows('charter_type_benefits');
    }
    
    $html .= '</div>';
  }
  $html .= '</div>';
  
  return $html;
});

/* ========================================
 * [ssyc_map] - Interactive Map
 * ======================================== */
add_shortcode('ssyc_map', function($atts){
  ssyc_enqueue_assets(true); // Load assets + Leaflet for maps
  $pid = get_the_ID();
  $source = ssyc_get('map_source', $pid) ?: 'from_featured_itinerary';
  $height = ssyc_get('map_height', $pid) ?: 420;
  $theme = ssyc_get('map_theme', $pid) ?: 'light';
  
  if ($source === 'none') return '';
  
  $geojson = '';
  
  if ($source === 'manual_geojson') {
    $geojson = ssyc_get('map_geojson', $pid);
  } elseif ($source === 'from_featured_itinerary') {
    $itinerary_id = ssyc_get('featured_itinerary', $pid);
    if ($itinerary_id) {
      $geojson = get_post_meta($itinerary_id, 'ssi_map_geojson', true);
    }
  }
  
  if (!$geojson) return '';
  
  // Use itineraries map class so it's handled by existing ssi-v3.js
  return '<div class="ssyc-map ssi-map-geojson" style="height:'.(int)$height.'px;" data-geojson="'.esc_attr($geojson).'" data-theme="'.esc_attr($theme).'" data-autofit="1"></div>';
});

/* ========================================
 * [ssyc_weather] - Weather Summary
 * ======================================== */
add_shortcode('ssyc_weather', function($atts){
  ssyc_enqueue_assets();
  $pid = get_the_ID();
  $enabled = ssyc_get('weather_enable', $pid);
  if (!$enabled) return '';
  
  return ssyc_fetch_weather($pid);
});

/* ========================================
 * [ssyc_pricing] - Pricing Guide Table
 * ======================================== */
add_shortcode('ssyc_pricing', function($atts){
  ssyc_enqueue_assets();
  $pid = get_the_ID();
  if ( ! function_exists('have_rows') ) return '';
  
  $currency = ssyc_get('currency_code', $pid) ?: 'EUR';
  $notes = ssyc_get('pricing_notes', $pid);
  
  $html = '';
  if ( have_rows('pricing_table', $pid) ) {
    $html .= '<div class="ssyc-pricing">';
    $html .= '<table class="ssyc-pricing-table">';
    $html .= '<thead><tr><th>Season</th><th>Bareboat</th><th>Catamaran</th><th>Crewed</th></tr></thead>';
    $html .= '<tbody>';
    
    while ( have_rows('pricing_table', $pid) ) { the_row();
      $season = get_sub_field('season_label');
      $bareboat = get_sub_field('bareboat_from');
      $catamaran = get_sub_field('catamaran_from');
      $crewed = get_sub_field('crewed_from');
      
      $html .= '<tr>';
      $html .= '<td>'.esc_html($season).'</td>';
      $html .= '<td>'.($bareboat ? esc_html($currency.' '.number_format($bareboat)) : '—').'</td>';
      $html .= '<td>'.($catamaran ? esc_html($currency.' '.number_format($catamaran)) : '—').'</td>';
      $html .= '<td>'.($crewed ? esc_html($currency.' '.number_format($crewed)) : '—').'</td>';
      $html .= '</tr>';
    }
    
    $html .= '</tbody></table>';
    if ($notes) $html .= '<div class="ssyc-pricing-notes">'.wp_kses_post($notes).'</div>';
    $html .= '</div>';
    
    if ( function_exists('reset_rows') ) reset_rows('pricing_table');
  }
  
  return $html;
});

/* ========================================
 * [ssyc_process] - How It Works Steps
 * ======================================== */
add_shortcode('ssyc_process', function($atts){
  ssyc_enqueue_assets();
  $pid = get_the_ID();
  if ( ! function_exists('have_rows') ) return '';
  
  $html = '';
  if ( have_rows('process_steps', $pid) ) {
    $html .= '<div class="ssyc-process">';
    $step_num = 1;
    
    while ( have_rows('process_steps', $pid) ) { the_row();
      $title = get_sub_field('step_title');
      $summary = get_sub_field('step_summary');
      $icon = get_sub_field('step_icon');
      
      $html .= '<div class="ssyc-process-step">';
      $html .= '<div class="ssyc-step-number">'.esc_html($step_num).'</div>';
      if ($icon) $html .= '<div class="ssyc-step-icon">'.ssyc_svg($icon, '#0ea5e9', 40).'</div>';
      $html .= '<h3 class="ssyc-step-title">'.esc_html($title).'</h3>';
      if ($summary) $html .= '<p class="ssyc-step-summary">'.esc_html($summary).'</p>';
      $html .= '</div>';
      
      $step_num++;
    }
    
    $html .= '</div>';
    if ( function_exists('reset_rows') ) reset_rows('process_steps');
  }
  
  return $html;
});

/* ========================================
 * [ssyc_why_us] - Why Book With Us
 * ======================================== */
add_shortcode('ssyc_why_us', function($atts){
  ssyc_enqueue_assets();
  $pid = get_the_ID();
  $content = ssyc_get('why_us_html', $pid);
  
  $html = '<div class="ssyc-why-us">';
  if ($content) $html .= wp_kses_post($content);
  
  // Trust badges
  if ( function_exists('have_rows') && have_rows('trust_badges', $pid) ) {
    $html .= '<div class="ssyc-trust-badges">';
    while ( have_rows('trust_badges', $pid) ) { the_row();
      $image = get_sub_field('badge_image');
      $alt = get_sub_field('badge_alt');
      
      if (is_array($image) && !empty($image['url'])) {
        $html .= '<img src="'.esc_url($image['url']).'" alt="'.esc_attr($alt).'" class="ssyc-badge">';
      }
    }
    $html .= '</div>';
    if ( function_exists('reset_rows') ) reset_rows('trust_badges');
  }
  
  $html .= '</div>';
  return $html;
});

/* ========================================
 * [ssyc_reviews] - Reviews/Trustpilot
 * ======================================== */
add_shortcode('ssyc_reviews', function($atts){
  ssyc_enqueue_assets();
  $pid = get_the_ID();
  $mode = ssyc_get('reviews_mode', $pid) ?: 'trustpilot_custom_v1';
  
  if ($mode === 'none') return '';
  
  if ($mode === 'trustpilot_custom_v1') {
    $headline = ssyc_get('tp_headline', $pid) ?: 'Rated 4.9★ on Trustpilot';
    $caption = ssyc_get('tp_caption', $pid) ?: '200+ verified reviews';
    $cta_label = ssyc_get('tp_cta_label', $pid) ?: 'Read Reviews';
    $cta_url = ssyc_get('tp_cta_url', $pid);
    $cta_url = $cta_url ? do_shortcode($cta_url) : '';
    $score = ssyc_get('tp_star_score', $pid) ?: 4.9;
    $count = ssyc_get('tp_review_count', $pid) ?: '200+';
    
    $html = '<div class="ssyc-reviews ssyc-reviews-tp">';
    $html .= '<div class="ssyc-tp-banner">';
    $html .= '<div class="ssyc-tp-stars">'.ssyc_render_stars($score).'</div>';
    $html .= '<h3 class="ssyc-tp-headline">'.esc_html($headline).'</h3>';
    $html .= '<p class="ssyc-tp-caption">'.esc_html($caption).'</p>';
    if ($cta_url) $html .= '<a href="'.esc_url($cta_url).'" class="ssyc-btn ssyc-btn-secondary" target="_blank" rel="noopener">'.esc_html($cta_label).'</a>';
    $html .= '</div></div>';
    
    return $html;
  }
  
  return '';
});

/* ========================================
 * [ssyc_faqs] - FAQ Accordion
 * ======================================== */
add_shortcode('ssyc_faqs', function($atts){
  ssyc_enqueue_assets(); // Load assets when shortcode is used
  $pid = get_the_ID();
  if ( ! function_exists('have_rows') ) return '';
  
  $html = '';
  if ( have_rows('faqs', $pid) ) {
    $html .= '<div class="ssyc-faqs">';
    $faq_num = 1;
    
    while ( have_rows('faqs', $pid) ) { the_row();
      $question = get_sub_field('faq_question');
      $answer = get_sub_field('faq_answer');
      
      $html .= '<div class="ssyc-faq-item">';
      $html .= '<button class="ssyc-faq-toggle" type="button" aria-expanded="false">';
      $html .= '<span class="ssyc-faq-question">'.esc_html($question).'</span>';
      $html .= '<span class="ssyc-faq-icon">'.ssyc_svg('expand_more', '#12305c', 18).'</span>';
      $html .= '</button>';
      $html .= '<div class="ssyc-faq-answer" hidden>'.wp_kses_post($answer).'</div>';
      $html .= '</div>';
      
      $faq_num++;
    }
    
    $html .= '</div>';
    if ( function_exists('reset_rows') ) reset_rows('faqs');
  }
  
  return $html;
});

/* ========================================
 * [ssyc_related_guides] - Related Guides
 * ======================================== */
add_shortcode('ssyc_related_guides', function($atts){
  ssyc_enqueue_assets(); // Load assets when shortcode is used
  $pid = get_the_ID();
  $by = ssyc_get('related_guides_by', $pid) ?: 'categories';
  
  $guides = [];
  if ($by === 'manual') {
    $guides = ssyc_get('related_guides_manual', $pid);
    if (!is_array($guides)) $guides = [];
  } elseif ($by === 'categories') {
    $cats = ssyc_get('related_guides_categories', $pid);
    $limit = ssyc_get('related_guides_limit', $pid) ?: 4;
    
    if ($cats && is_array($cats)) {
      // Ensure $cats is array of integers
      $cats = array_map('intval', $cats);
      
      $args = [
        'post_type' => 'destinations', // Guides are destinations CPT
        'posts_per_page' => $limit,
        'tax_query' => [[
          'taxonomy' => 'category', // Destinations use standard WP categories, not product_cat
          'field' => 'term_id',
          'terms' => $cats,
        ]],
      ];
      $query = new WP_Query($args);
      if ($query->have_posts()) {
        while ($query->have_posts()) {
          $query->the_post();
          $guides[] = get_the_ID();
        }
        wp_reset_postdata();
      }
    }
  }
  
  if (empty($guides)) return '';
  
  $html = '<div class="ssyc-related-guides"><h2>Related Guides</h2><div class="ssyc-grid">';
  foreach ($guides as $guide_id) {
    $title = get_the_title($guide_id);
    $url = get_permalink($guide_id);
    $thumb = get_the_post_thumbnail_url($guide_id, 'medium');
    $excerpt = get_the_excerpt($guide_id);
    
    $html .= '<div class="ssyc-card">';
    if ($thumb) $html .= '<div class="ssyc-card-image" style="background-image:url(\''.esc_url($thumb).'\');"></div>';
    $html .= '<div class="ssyc-card-body">';
    $html .= '<h3 class="ssyc-card-title"><a href="'.esc_url($url).'">'.esc_html($title).'</a></h3>';
    if ($excerpt) $html .= '<p class="ssyc-card-excerpt">'.esc_html(wp_trim_words($excerpt, 20)).'</p>';
    $html .= '</div></div>';
  }
  $html .= '</div></div>';
  
  return $html;
});

/* ========================================
 * [ssyc_related_itineraries] - Related Itineraries
 * ======================================== */
add_shortcode('ssyc_related_itineraries', function($atts){
  ssyc_enqueue_assets(); // Load assets when shortcode is used
  $pid = get_the_ID();
  $by = ssyc_get('related_itineraries_by', $pid) ?: 'categories';
  $featured_id = ssyc_get('featured_itinerary', $pid);
  
  $itineraries = [];
  if ($by === 'manual') {
    $itineraries = ssyc_get('related_itineraries_manual', $pid);
    if (!is_array($itineraries)) $itineraries = [];
  } elseif ($by === 'categories') {
    $cats = ssyc_get('related_itineraries_categories', $pid);
    $limit = ssyc_get('related_itineraries_limit', $pid) ?: 3;
    
    if ($cats && is_array($cats)) {
      // Ensure $cats is array of integers
      $cats = array_map('intval', $cats);
      
      $args = [
        'post_type' => 'itinerary',
        'posts_per_page' => $limit + 1, // Get extra in case we need to exclude featured
        'tax_query' => [[
          'taxonomy' => 'product_cat',
          'field' => 'term_id',
          'terms' => $cats,
        ]],
      ];
      if ($featured_id) {
        $args['post__not_in'] = [$featured_id];
      }
      
      $query = new WP_Query($args);
      if ($query->have_posts()) {
        $count = 0;
        while ($query->have_posts() && $count < $limit) {
          $query->the_post();
          $itin_id = get_the_ID();
          if ($itin_id != $featured_id) {
            $itineraries[] = $itin_id;
            $count++;
          }
        }
        wp_reset_postdata();
      }
    }
  }
  
  // Remove featured from manual list too
  if ($featured_id && in_array($featured_id, $itineraries)) {
    $itineraries = array_diff($itineraries, [$featured_id]);
  }
  
  if (empty($itineraries)) return '';
  
  $html = '<div class="ssyc-related-itineraries"><h2>Related Itineraries</h2><div class="ssyc-grid">';
  foreach ($itineraries as $itin_id) {
    $title = get_the_title($itin_id);
    $url = get_permalink($itin_id);
    $thumb = get_the_post_thumbnail_url($itin_id, 'medium');
    $subtitle = get_post_meta($itin_id, 'ssi_subtitle', true);
    
    $html .= '<div class="ssyc-card">';
    if ($thumb) $html .= '<div class="ssyc-card-image" style="background-image:url(\''.esc_url($thumb).'\');"></div>';
    $html .= '<div class="ssyc-card-body">';
    $html .= '<h3 class="ssyc-card-title"><a href="'.esc_url($url).'">'.esc_html($title).'</a></h3>';
    if ($subtitle) $html .= '<p class="ssyc-card-subtitle">'.esc_html($subtitle).'</p>';
    $html .= '</div></div>';
  }
  $html .= '</div></div>';
  
  return $html;
});

/* ========================================
 * [ssyc_footer_cta] - Footer CTA
 * ======================================== */
add_shortcode('ssyc_footer_cta', function($atts){
  ssyc_enqueue_assets();
  $pid = get_the_ID();
  $heading = ssyc_get('footer_cta_heading', $pid);
  $subtext = ssyc_get('footer_cta_subtext', $pid);
  
  if (!$heading && !$subtext) return '';
  
  $html = '<div class="ssyc-footer-cta">';
  if ($heading) $html .= '<h2 class="ssyc-footer-cta-heading">'.esc_html($heading).'</h2>';
  if ($subtext) $html .= '<p class="ssyc-footer-cta-subtext">'.esc_html($subtext).'</p>';
  $html .= '</div>';
  
  return $html;
});

/* ========================================
 * [ssyc_lead_form] - Lead Form Wrapper
 * ======================================== */
add_shortcode('ssyc_lead_form', function($atts){
  $pid = get_the_ID();
  $shortcode = ssyc_get('form_shortcode', $pid) ?: '[sailscanner_lead_form]';
  $position = ssyc_get('form_insert_position', $pid) ?: 'sidebar_desktop';
  
  $classes = 'ssyc-form-wrap ssyc-form-pos-'.esc_attr($position);
  
  $html = '<div id="yacht-charter-form" class="'.esc_attr($classes).'">';
  $html .= do_shortcode($shortcode);
  $html .= '</div>';
  
  return $html;
});


