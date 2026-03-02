<?php
/**
 * SEO for proposal and ss_proposal_yacht pages.
 *
 * - Noindex/nofollow meta + X-Robots-Tag header.
 * - Sitemap/search exclusion (WordPress core, Yoast, RankMath).
 * - OG / social sharing meta for proposal token pages (since the token route is a
 *   custom query_var, not a standard singular query, and is invisible to RankMath).
 * - Document <title> override so RankMath/Yoast don't fall back to generic site meta.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class SS_Proposal_SEO {

	public static function init() {
		add_action( 'wp_head', [ __CLASS__, 'noindex_meta' ], 1 );
		add_action( 'template_redirect', [ __CLASS__, 'noindex_header' ], 0 );
		add_filter( 'pre_get_posts', [ __CLASS__, 'exclude_from_search' ] );
		add_filter( 'wp_sitemaps_post_types', [ __CLASS__, 'exclude_from_sitemaps' ] );

		// Yoast sitemap exclusion
		add_filter( 'wpseo_sitemap_exclude_post_type', [ __CLASS__, 'yoast_exclude_post_type' ], 10, 2 );
		add_filter( 'wpseo_exclude_from_sitemap_by_post_ids', [ __CLASS__, 'yoast_exclude_proposal_ids' ], 10, 1 );

		// RankMath sitemap exclusion
		add_filter( 'rank_math/sitemap/exclude_post_type', [ __CLASS__, 'rankmath_exclude_post_type' ], 10, 2 );

		// Social / OG tags for the proposal token page.
		// This must fire on wp (query vars are available; $ss_proposal_post not yet set).
		add_action( 'wp', [ __CLASS__, 'suppress_third_party_og_for_proposal' ], 5 );

		// Output our own OG tags early — social crawlers use the first occurrence.
		add_action( 'wp_head', [ __CLASS__, 'proposal_og_tags' ], 1 );

		// Override the <title> tag so RankMath/Yoast don't fall back to site or archive title.
		add_filter( 'pre_get_document_title', [ __CLASS__, 'proposal_document_title' ] );
	}

	/* -------------------------------------------------------------------------
	 * Noindex / robots
	 * ---------------------------------------------------------------------- */

	public static function noindex_meta() {
		if ( get_query_var( 'ss_proposal_token', false ) || is_singular( 'ss_proposal_yacht' ) ) {
			echo '<meta name="robots" content="noindex, nofollow" />' . "\n";
		}
	}

	public static function noindex_header() {
		if ( get_query_var( 'ss_proposal_token', false ) || is_singular( 'ss_proposal_yacht' ) ) {
			if ( ! headers_sent() ) {
				header( 'X-Robots-Tag: noindex, nofollow' );
			}
		}
	}

	/* -------------------------------------------------------------------------
	 * Sitemap / search exclusion
	 * ---------------------------------------------------------------------- */

	public static function exclude_from_search( WP_Query $query ) {
		if ( is_admin() || ! $query->is_main_query() || ! $query->is_search() ) {
			return;
		}
		$pt      = $query->get( 'post_type' );
		$exclude = [ 'ss_proposal', 'ss_proposal_yacht' ];
		if ( is_array( $pt ) ) {
			$query->set( 'post_type', array_values( array_diff( $pt, $exclude ) ) );
		} else {
			$public = array_keys( get_post_types( [ 'public' => true ], 'names' ) );
			$query->set( 'post_type', array_values( array_diff( $public, $exclude ) ) );
		}
	}

	public static function exclude_from_sitemaps( $post_types ) {
		unset( $post_types['ss_proposal'] );
		unset( $post_types['ss_proposal_yacht'] );
		return $post_types;
	}

	public static function yoast_exclude_post_type( $exclude, $post_type ) {
		if ( in_array( $post_type, [ 'ss_proposal', 'ss_proposal_yacht' ], true ) ) {
			return true;
		}
		return $exclude;
	}

	public static function yoast_exclude_proposal_ids( $ids ) {
		$posts = get_posts( [
			'post_type'      => 'ss_proposal',
			'post_status'    => 'any',
			'posts_per_page' => -1,
			'fields'         => 'ids',
		] );
		$yachts = get_posts( [
			'post_type'      => 'ss_proposal_yacht',
			'post_status'    => 'any',
			'posts_per_page' => -1,
			'fields'         => 'ids',
		] );
		return array_merge( (array) $ids, $posts, $yachts );
	}

	public static function rankmath_exclude_post_type( $exclude, $post_type ) {
		if ( in_array( $post_type, [ 'ss_proposal', 'ss_proposal_yacht' ], true ) ) {
			return true;
		}
		return $exclude;
	}

	/* -------------------------------------------------------------------------
	 * Social / OG tags for proposal token pages
	 *
	 * Background: proposals are served via a custom rewrite rule that sets the
	 * ss_proposal_token query var. WordPress never runs a standard singular
	 * WP_Query for an ss_proposal post, so RankMath and Yoast have no context
	 * for the page and fall back to generic site/archive meta. The CPT is also
	 * publicly_queryable=false, so it is invisible in RankMath's UI.
	 *
	 * We therefore output our own OG tags at wp_head priority 1 (social crawlers
	 * honour the FIRST occurrence) and disable the SEO plugins' OG output for
	 * this page type.
	 * ---------------------------------------------------------------------- */

	/**
	 * Run on the wp action (query vars available). Adds filters to prevent
	 * RankMath and Yoast from emitting OG / title tags for proposal pages —
	 * our own output (priority 1 on wp_head) takes precedence.
	 */
	public static function suppress_third_party_og_for_proposal() {
		if ( ! get_query_var( 'ss_proposal_token', false ) ) {
			return;
		}

		// ---- RankMath ----
		// Disable OG/social output. Filter names are stable across RM 1.x.
		add_filter( 'rank_math/opengraph/facebook_enabled', '__return_false' );
		add_filter( 'rank_math/opengraph/twitter_enabled', '__return_false' );
		// Override RM title so it doesn't fall back to site/home title
		add_filter( 'rank_math/frontend/title', [ __CLASS__, 'get_proposal_seo_title' ] );

		// ---- Yoast SEO ----
		add_filter( 'wpseo_output_og', '__return_false' );
		add_filter( 'wpseo_title', [ __CLASS__, 'get_proposal_seo_title' ] );
	}

	/** Shared title string for RankMath and Yoast title filters. */
	public static function get_proposal_seo_title( $title ) {
		if ( get_query_var( 'ss_proposal_token', false ) ) {
			return __( 'Charter Proposal', 'sailscanner-proposals' ) . ' | ' . get_bloginfo( 'name' );
		}
		return $title;
	}

	/**
	 * Override the WordPress document <title> for proposal pages.
	 * Fires on pre_get_document_title (WP 4.4+).
	 */
	public static function proposal_document_title( $title ) {
		if ( get_query_var( 'ss_proposal_token', false ) ) {
			return __( 'Charter Proposal', 'sailscanner-proposals' ) . ' | ' . get_bloginfo( 'name' );
		}
		return $title;
	}

	/**
	 * Output Open Graph and Twitter Card meta for the proposal token page.
	 * Runs at wp_head priority 1 — before RankMath, Yoast, or any theme output.
	 *
	 * Title and description are intentionally generic (no client name, no prices)
	 * since social crawlers can index og:image/title even for noindex pages.
	 * The first real yacht photo from the proposal is used as og:image if available.
	 */
	public static function proposal_og_tags() {
		$token = get_query_var( 'ss_proposal_token', false );
		if ( ! $token ) {
			return;
		}

		global $ss_proposal_post;
		if ( ! $ss_proposal_post ) {
			return;
		}

		$proposal_id = (int) $ss_proposal_post->ID;
		$site_name   = get_bloginfo( 'name' );
		$og_title    = __( 'Charter Proposal', 'sailscanner-proposals' ) . ' | ' . $site_name;
		$og_desc     = __( 'View your personalised yacht charter proposal from SailScanner — tailored options prepared just for you.', 'sailscanner-proposals' );
		$og_url      = home_url( '/proposals/' . rawurlencode( $token ) . '/' );
		$og_image    = '';

		// Use the first real yacht photo as og:image (looks great in link previews).
		$yacht_ids = get_post_meta( $proposal_id, 'ss_yacht_ids', true );
		if ( is_array( $yacht_ids ) && ! empty( $yacht_ids ) ) {
			foreach ( $yacht_ids as $yid ) {
				$images_json = get_post_meta( (int) $yid, 'images_json', true );
				if ( ! is_string( $images_json ) ) {
					continue;
				}
				$imgs = json_decode( $images_json, true );
				if ( ! is_array( $imgs ) ) {
					continue;
				}
				foreach ( $imgs as $img ) {
					$candidate = is_string( $img ) ? $img : ( $img['url'] ?? '' );
					if ( $candidate && SS_Proposal_Helpers::is_real_yacht_image( $candidate ) ) {
						$og_image = esc_url( $candidate );
						break 2;
					}
				}
			}
		}

		// Fallback: site icon (512px+).
		if ( ! $og_image ) {
			$icon = get_site_icon_url( 512 );
			if ( $icon ) {
				$og_image = $icon;
			}
		}

		echo "\n<!-- SailScanner Proposal: social sharing meta -->\n";
		echo '<meta property="og:title" content="' . esc_attr( $og_title ) . '" />' . "\n";
		echo '<meta property="og:description" content="' . esc_attr( $og_desc ) . '" />' . "\n";
		echo '<meta property="og:type" content="website" />' . "\n";
		echo '<meta property="og:url" content="' . esc_url( $og_url ) . '" />' . "\n";
		echo '<meta property="og:site_name" content="' . esc_attr( $site_name ) . '" />' . "\n";
		if ( $og_image ) {
			echo '<meta property="og:image" content="' . esc_url( $og_image ) . '" />' . "\n";
			echo '<meta property="og:image:width" content="1200" />' . "\n";
			echo '<meta property="og:image:height" content="630" />' . "\n";
		}
		echo '<meta name="twitter:card" content="summary_large_image" />' . "\n";
		echo '<meta name="twitter:title" content="' . esc_attr( $og_title ) . '" />' . "\n";
		echo '<meta name="twitter:description" content="' . esc_attr( $og_desc ) . '" />' . "\n";
		if ( $og_image ) {
			echo '<meta name="twitter:image" content="' . esc_url( $og_image ) . '" />' . "\n";
		}
		echo '<link rel="canonical" href="' . esc_url( $og_url ) . '" />' . "\n";
	}
}
