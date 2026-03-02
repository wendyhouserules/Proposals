<?php
/**
 * Token-based routing: /proposals/{token}/ resolves by meta ss_token. Template loader for ss_proposal and ss_proposal_yacht.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class SS_Proposal_Routing {

	public static function init() {
		add_action( 'init', [ __CLASS__, 'add_rewrite_rule' ], 10 );
		add_filter( 'template_include', [ __CLASS__, 'template_include' ], 99 );
		add_action( 'template_redirect', [ __CLASS__, 'resolve_proposal_token' ], 1 );
	}

	public static function add_rewrite_rule() {
		add_rewrite_rule(
			'^proposals/([a-zA-Z0-9_-]{32,48})/?$',
			'index.php?ss_proposal_token=$matches[1]',
			'top'
		);
		add_filter( 'query_vars', function ( $vars ) {
			$vars[] = 'ss_proposal_token';
			return $vars;
		} );
	}

	/**
	 * Resolve token to proposal post; set global and 404 if invalid/missing.
	 */
	public static function resolve_proposal_token() {
		$token = get_query_var( 'ss_proposal_token', false );
		if ( ! $token ) {
			return;
		}

		$posts = get_posts( [
			'post_type'      => 'ss_proposal',
			'post_status'    => [ 'publish', 'draft', 'private' ],
			'posts_per_page' => 1,
			'meta_key'       => 'ss_token',
			'meta_value'     => sanitize_text_field( $token ),
			'fields'         => 'ids',
		] );

		if ( empty( $posts ) ) {
			if ( defined( 'SAILSCANNER_PROPOSALS_DEBUG' ) && SAILSCANNER_PROPOSALS_DEBUG ) {
				// phpcs:ignore WordPress.PHP.DevelopmentFunctions.error_log_error_log
				error_log( 'SS Proposals: no proposal found for token (length ' . strlen( $token ) . ')' );
			}
			global $wp_query;
			$wp_query->set_404();
			status_header( 404 );
			nocache_headers();
			return;
		}

		$proposal_id = (int) $posts[0];
		$status      = get_post_status( $proposal_id );
		if ( $status !== 'publish' ) {
			global $wp_query;
			$wp_query->set_404();
			status_header( 404 );
			nocache_headers();
			return;
		}

		global $ss_proposal_post;
		$ss_proposal_post = get_post( $proposal_id );
	}

	/**
	 * Load plugin templates for ss_proposal (token view) and single ss_proposal_yacht.
	 */
	public static function template_include( $template ) {
		$token = get_query_var( 'ss_proposal_token', false );
		if ( $token ) {
			$proposal_template = SAILSCANNER_PROPOSALS_PATH . 'templates/single-ss-proposal.php';
			if ( file_exists( $proposal_template ) ) {
				return $proposal_template;
			}
		}

		if ( is_singular( 'ss_proposal_yacht' ) ) {
			$proposal_yacht_template = SAILSCANNER_PROPOSALS_PATH . 'templates/single-ss-proposal-yacht.php';
			if ( file_exists( $proposal_yacht_template ) ) {
				return $proposal_yacht_template;
			}
		}

		return $template;
	}
}
