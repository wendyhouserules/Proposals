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
		add_action( 'admin_bar_menu',    [ __CLASS__, 'add_edit_admin_bar_link' ], 80 );

		// Admin: "View Proposal" link in list-view row actions and edit-screen meta box.
		add_filter( 'post_row_actions',  [ __CLASS__, 'add_list_view_row_action' ], 10, 2 );
		add_action( 'add_meta_boxes',    [ __CLASS__, 'add_view_proposal_meta_box' ] );
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
	 * Add an "Edit Proposal" link to the WP admin bar when viewing a token-based proposal page.
	 * WordPress can't add this automatically because the token route doesn't set $post.
	 *
	 * @param WP_Admin_Bar $wp_admin_bar
	 */
	public static function add_edit_admin_bar_link( $wp_admin_bar ) {
		if ( ! is_admin_bar_showing() ) {
			return;
		}

		// Only act on token-based proposal pages.
		$token = get_query_var( 'ss_proposal_token', false );
		if ( ! $token ) {
			return;
		}

		global $ss_proposal_post;
		if ( ! $ss_proposal_post || ! ( $ss_proposal_post instanceof WP_Post ) ) {
			return;
		}

		$proposal_id = $ss_proposal_post->ID;
		if ( ! current_user_can( 'edit_post', $proposal_id ) ) {
			return;
		}

		$edit_url = get_edit_post_link( $proposal_id );
		if ( ! $edit_url ) {
			return;
		}

		$wp_admin_bar->add_node( [
			'id'    => 'ss-edit-proposal',
			'title' => '<span class="ab-icon dashicons dashicons-edit" aria-hidden="true"></span>'
			           . __( 'Edit Proposal', 'sailscanner-proposals' ),
			'href'  => $edit_url,
			'meta'  => [
				'title' => __( 'Edit this proposal in the WordPress admin', 'sailscanner-proposals' ),
			],
		] );
	}

	/**
	 * Helper: build the token-based front-end URL for a proposal post.
	 * Returns empty string if no token is stored yet.
	 */
	private static function get_proposal_url( int $post_id ): string {
		$token = get_post_meta( $post_id, 'ss_token', true );
		if ( ! $token ) {
			return '';
		}
		return user_trailingslashit( home_url( '/proposals/' . $token . '/' ) );
	}

	/**
	 * Add a "View Proposal" link in the CPT list-view row actions.
	 *
	 * @param array   $actions Existing row actions.
	 * @param WP_Post $post    Current post object.
	 * @return array
	 */
	public static function add_list_view_row_action( array $actions, WP_Post $post ): array {
		if ( $post->post_type !== 'ss_proposal' ) {
			return $actions;
		}
		$url = self::get_proposal_url( $post->ID );
		if ( ! $url ) {
			return $actions;
		}
		$actions['view_proposal'] = sprintf(
			'<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>',
			esc_url( $url ),
			esc_html__( 'View Proposal', 'sailscanner-proposals' )
		);
		return $actions;
	}

	/**
	 * Register a small meta box on the ss_proposal edit screen with a direct "View Proposal" button.
	 */
	public static function add_view_proposal_meta_box(): void {
		add_meta_box(
			'ss_proposal_view_link',
			__( 'Proposal Link', 'sailscanner-proposals' ),
			[ __CLASS__, 'render_view_proposal_meta_box' ],
			'ss_proposal',
			'side',
			'high'
		);
	}

	/**
	 * Render the "Proposal Link" meta box content.
	 *
	 * @param WP_Post $post Current post.
	 */
	public static function render_view_proposal_meta_box( WP_Post $post ): void {
		$url = self::get_proposal_url( $post->ID );
		if ( ! $url ) {
			echo '<p style="color:#888;">' . esc_html__( 'No token yet — save the proposal first.', 'sailscanner-proposals' ) . '</p>';
			return;
		}
		printf(
			'<p><a href="%1$s" target="_blank" rel="noopener noreferrer" class="button button-primary" style="width:100%%;text-align:center;">%2$s</a></p>
			<p style="word-break:break-all;font-size:11px;color:#555;margin-top:4px;"><a href="%1$s" target="_blank" rel="noopener noreferrer">%1$s</a></p>',
			esc_url( $url ),
			esc_html__( 'View Proposal ↗', 'sailscanner-proposals' )
		);
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
