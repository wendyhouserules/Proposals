<?php
/**
 * Registers ss_proposal CPT. Publicly renderable but not discoverable; no archive; excluded from search/sitemap.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class SS_Proposal_CPT {

	public static function init() {
		add_action( 'init',           [ __CLASS__, 'register_cpt' ], 5 );
		add_action( 'add_meta_boxes', [ __CLASS__, 'add_meta_boxes' ] );
		add_action( 'save_post',      [ __CLASS__, 'save_requirements_meta_box' ], 10, 2 );
		add_action( 'save_post',      [ __CLASS__, 'save_itinerary_meta_box' ], 10, 2 );
		add_action( 'save_post',      [ __CLASS__, 'save_yacht_gallery_meta_box' ], 10, 2 );
		add_action( 'save_post',      [ __CLASS__, 'save_yacht_details_meta_box' ], 10, 2 );
		add_action( 'save_post',      [ __CLASS__, 'save_yacht_pricing_meta_box' ], 10, 2 );
		add_action( 'admin_enqueue_scripts', [ __CLASS__, 'enqueue_yacht_gallery_scripts' ] );
	}

	public static function register_cpt() {
		$labels = [
			'name'               => _x( 'Proposals', 'post type general name', 'sailscanner-proposals' ),
			'singular_name'      => _x( 'Proposal', 'post type singular name', 'sailscanner-proposals' ),
			'menu_name'          => __( 'Proposals', 'sailscanner-proposals' ),
			'add_new'            => __( 'Add New', 'sailscanner-proposals' ),
			'add_new_item'       => __( 'Add New Proposal', 'sailscanner-proposals' ),
			'edit_item'          => __( 'Edit Proposal', 'sailscanner-proposals' ),
			'view_item'          => __( 'View Proposal', 'sailscanner-proposals' ),
			'all_items'          => __( 'All Proposals', 'sailscanner-proposals' ),
			'search_items'       => __( 'Search Proposals', 'sailscanner-proposals' ),
			'not_found'          => __( 'No proposals found.', 'sailscanner-proposals' ),
			'not_found_in_trash' => __( 'No proposals found in Trash.', 'sailscanner-proposals' ),
		];

		$args = [
			'labels'              => $labels,
			'public'              => true,
			'publicly_queryable'  => false, // Served via token route, not ?post_type=ss_proposal&p=123
			'show_ui'             => true,
			'show_in_menu'        => true,
			'show_in_rest'        => true,
			'rewrite'             => false,
			'has_archive'         => false,
			'exclude_from_search' => true,
			'capability_type'     => 'post',
			'map_meta_cap'        => true,
			'supports'            => [ 'title', 'editor' ],
			'menu_icon'           => 'dashicons-media-document',
		];

		register_post_type( 'ss_proposal', $args );

		// Proposal yacht picks: one post per yacht so "View details" has a real URL. Not for guide content.
		register_post_type( 'ss_proposal_yacht', [
			'labels'              => [
				'name'               => _x( 'Proposal Yachts', 'post type general name', 'sailscanner-proposals' ),
				'singular_name'      => _x( 'Proposal Yacht', 'post type singular name', 'sailscanner-proposals' ),
				'menu_name'          => __( 'Proposal Yachts', 'sailscanner-proposals' ),
				'add_new'            => __( 'Add New', 'sailscanner-proposals' ),
				'add_new_item'       => __( 'Add New Proposal Yacht', 'sailscanner-proposals' ),
				'edit_item'          => __( 'Edit Proposal Yacht', 'sailscanner-proposals' ),
				'view_item'          => __( 'View Proposal Yacht', 'sailscanner-proposals' ),
				'all_items'          => __( 'All Proposal Yachts', 'sailscanner-proposals' ),
				'not_found'          => __( 'No proposal yachts found.', 'sailscanner-proposals' ),
			],
			'public'              => true,
			'publicly_queryable'  => true,
			'show_ui'             => true,
			'show_in_menu'        => true,
			'show_in_rest'        => true,
			'rewrite'             => [ 'slug' => 'proposal-yacht' ],
			'has_archive'         => false,
			'exclude_from_search' => true,
			'capability_type'     => 'post',
			'map_meta_cap'        => true,
			'supports'            => [ 'title' ],
			'menu_icon'           => 'dashicons-portfolio',
		] );
	}

	// ── Meta boxes ────────────────────────────────────────────────────────────

	public static function add_meta_boxes() {
		add_meta_box(
			'ss_proposal_requirements',
			__( 'Your Requirements (editable)', 'sailscanner-proposals' ),
			[ __CLASS__, 'render_requirements_meta_box' ],
			'ss_proposal',
			'normal',
			'high'
		);
		add_meta_box(
			'ss_proposal_itinerary',
			__( 'Example Itinerary', 'sailscanner-proposals' ),
			[ __CLASS__, 'render_itinerary_meta_box' ],
			'ss_proposal',
			'normal',
			'default'
		);
		add_meta_box(
			'ss_yacht_gallery',
			__( 'Gallery Images (Media Library)', 'sailscanner-proposals' ),
			[ __CLASS__, 'render_yacht_gallery_meta_box' ],
			'ss_proposal_yacht',
			'normal',
			'high'
		);
		add_meta_box(
			'ss_yacht_details',
			__( 'Yacht Details', 'sailscanner-proposals' ),
			[ __CLASS__, 'render_yacht_details_meta_box' ],
			'ss_proposal_yacht',
			'normal',
			'default'
		);
		add_meta_box(
			'ss_yacht_pricing',
			__( 'Pricing', 'sailscanner-proposals' ),
			[ __CLASS__, 'render_yacht_pricing_meta_box' ],
			'ss_proposal_yacht',
			'normal',
			'default'
		);
	}

	// ── Yacht gallery scripts ──────────────────────────────────────────────────

	public static function enqueue_yacht_gallery_scripts( $hook ) {
		global $post;
		if ( ! in_array( $hook, [ 'post.php', 'post-new.php' ], true ) ) {
			return;
		}
		if ( ! $post || $post->post_type !== 'ss_proposal_yacht' ) {
			return;
		}
		wp_enqueue_media();
		wp_enqueue_style(
			'ss-yacht-gallery-admin',
			SAILSCANNER_PROPOSALS_URL . 'assets/yacht-gallery-admin.css',
			[],
			SAILSCANNER_PROPOSALS_VERSION
		);
	}

	// ── Yacht gallery meta box ─────────────────────────────────────────────────

	public static function render_yacht_gallery_meta_box( WP_Post $post ) {
		wp_nonce_field( 'ss_yacht_gallery_save', 'ss_yacht_gallery_nonce' );
		$ids     = get_post_meta( $post->ID, 'ss_yacht_gallery_ids', true );
		$ids_arr = ( is_string( $ids ) && $ids !== '' ) ? array_filter( array_map( 'absint', explode( ',', $ids ) ) ) : [];

		// Count auto-fetched images still stored in images_json.
		$images_json_raw  = get_post_meta( $post->ID, 'images_json', true );
		$auto_image_count = 0;
		if ( is_string( $images_json_raw ) && $images_json_raw !== '' ) {
			$dec = json_decode( $images_json_raw, true );
			$auto_image_count = is_array( $dec ) ? count( $dec ) : 0;
		}
		?>
		<p class="ss-gallery-help">
			<?php esc_html_e( 'Images selected here appear first in the yacht gallery, before any auto-fetched images. Drag to reorder.', 'sailscanner-proposals' ); ?>
		</p>

		<?php if ( $auto_image_count > 0 ) : ?>
		<div class="ss-gallery-autofetch-notice">
			<label>
				<input type="checkbox" name="ss_yacht_clear_auto_images" value="1" />
				<?php
				printf(
					/* translators: %d: number of auto-fetched images */
					esc_html( _n(
						'Remove %d auto-fetched image (imported from MMK — use this to clear broken or expired images)',
						'Remove %d auto-fetched images (imported from MMK — use this to clear broken or expired images)',
						$auto_image_count,
						'sailscanner-proposals'
					) ),
					(int) $auto_image_count
				);
				?>
			</label>
		</div>
		<?php endif; ?>

		<div class="ss-gallery-wrap">
			<ul id="ss-yacht-gallery-list" class="ss-gallery-list">
				<?php foreach ( $ids_arr as $att_id ) :
					$thumb = wp_get_attachment_image_url( $att_id, 'thumbnail' );
					if ( ! $thumb ) continue;
				?>
				<li class="ss-gallery-item" data-id="<?php echo absint( $att_id ); ?>">
					<img src="<?php echo esc_url( $thumb ); ?>" alt="" />
					<button type="button" class="ss-gallery-remove" aria-label="<?php esc_attr_e( 'Remove image', 'sailscanner-proposals' ); ?>">&#x2715;</button>
				</li>
				<?php endforeach; ?>
			</ul>

			<input type="hidden" id="ss_yacht_gallery_ids" name="ss_yacht_gallery_ids"
				value="<?php echo esc_attr( implode( ',', $ids_arr ) ); ?>" />

			<button type="button" id="ss-yacht-gallery-add" class="button">
				<?php esc_html_e( '+ Add Images', 'sailscanner-proposals' ); ?>
			</button>
		</div>

		<script>
		(function ($) {
			var frame;
			var $list  = $('#ss-yacht-gallery-list');
			var $input = $('#ss_yacht_gallery_ids');

			function syncIds() {
				var ids = $list.find('.ss-gallery-item').map(function () {
					return $(this).data('id');
				}).get();
				$input.val(ids.join(','));
			}

			// Add images via media library.
			$('#ss-yacht-gallery-add').on('click', function () {
				if (frame) { frame.open(); return; }
				frame = wp.media({
					title: '<?php echo esc_js( __( 'Select Gallery Images', 'sailscanner-proposals' ) ); ?>',
					button: { text: '<?php echo esc_js( __( 'Add to Gallery', 'sailscanner-proposals' ) ); ?>' },
					multiple: true,
					library: { type: 'image' }
				});
				frame.on('select', function () {
					frame.state().get('selection').each(function (attachment) {
						var id    = attachment.id;
						var thumb = attachment.attributes.sizes && attachment.attributes.sizes.thumbnail
							? attachment.attributes.sizes.thumbnail.url
							: attachment.attributes.url;
						// Skip duplicates.
						if ($list.find('[data-id="' + id + '"]').length) return;
						$list.append(
							'<li class="ss-gallery-item" data-id="' + id + '">' +
							'<img src="' + thumb + '" alt="" />' +
							'<button type="button" class="ss-gallery-remove" aria-label="Remove">&#x2715;</button>' +
							'</li>'
						);
					});
					syncIds();
				});
				frame.open();
			});

			// Remove image.
			$list.on('click', '.ss-gallery-remove', function () {
				$(this).closest('.ss-gallery-item').remove();
				syncIds();
			});

			// Drag-to-reorder via native HTML5 drag (simple swap approach).
			var dragged = null;
			$list.on('dragstart', '.ss-gallery-item', function (e) {
				dragged = this;
				e.originalEvent.dataTransfer.effectAllowed = 'move';
				$(this).addClass('ss-dragging');
			});
			$list.on('dragend', '.ss-gallery-item', function () {
				$(this).removeClass('ss-dragging');
				dragged = null;
				syncIds();
			});
			$list.on('dragover', '.ss-gallery-item', function (e) {
				e.preventDefault();
				e.originalEvent.dataTransfer.dropEffect = 'move';
				if (dragged && dragged !== this) {
					var rect    = this.getBoundingClientRect();
					var midX    = rect.left + rect.width / 2;
					var clientX = e.originalEvent.clientX;
					if (clientX < midX) {
						$list[0].insertBefore(dragged, this);
					} else {
						$list[0].insertBefore(dragged, this.nextSibling);
					}
				}
			});
			// Make items draggable.
			$list.find('.ss-gallery-item').attr('draggable', 'true');
			$list.on('DOMNodeInserted', '.ss-gallery-item', function () {
				$(this).attr('draggable', 'true');
			});
		}(jQuery));
		</script>

		<?php
		// ── Layout / deck plan image ──────────────────────────────────────────
		$layout_id  = (int) get_post_meta( $post->ID, 'ss_yacht_layout_image_id', true );
		$layout_src = $layout_id ? wp_get_attachment_image_url( $layout_id, 'medium' ) : '';
		$layout_url_fallback = get_post_meta( $post->ID, 'layout_image_url', true );
		?>
		<hr style="margin:16px 0 14px;" />
		<p style="font-weight:600;margin:0 0 8px;"><?php esc_html_e( 'Deck Plan / Layout Image', 'sailscanner-proposals' ); ?></p>
		<p class="ss-gallery-help"><?php esc_html_e( 'Select a deck plan or layout image from the media library. Replaces any auto-fetched layout URL.', 'sailscanner-proposals' ); ?></p>

		<div class="ss-layout-picker">
			<div id="ss-layout-preview" style="<?php echo $layout_src ? '' : 'display:none;'; ?>margin-bottom:8px;">
				<img id="ss-layout-img" src="<?php echo esc_url( $layout_src ); ?>" alt="" style="max-width:320px;max-height:200px;display:block;border-radius:6px;border:1px solid #e5e7eb;" />
			</div>
			<input type="hidden" id="ss_yacht_layout_image_id" name="ss_yacht_layout_image_id" value="<?php echo absint( $layout_id ); ?>" />
			<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
				<button type="button" id="ss-layout-pick" class="button"><?php esc_html_e( 'Choose Layout Image', 'sailscanner-proposals' ); ?></button>
				<?php if ( $layout_src || $layout_url_fallback ) : ?>
				<button type="button" id="ss-layout-remove" class="button-link-delete"><?php esc_html_e( 'Remove', 'sailscanner-proposals' ); ?></button>
				<?php endif; ?>
			</div>
			<?php if ( ! $layout_src && $layout_url_fallback ) : ?>
			<p style="margin:8px 0 0;font-size:12px;color:#6b7280;">
				<?php esc_html_e( 'Current auto-fetched URL:', 'sailscanner-proposals' ); ?>
				<a href="<?php echo esc_url( $layout_url_fallback ); ?>" target="_blank" style="word-break:break-all;"><?php echo esc_url( $layout_url_fallback ); ?></a>
				<label style="display:block;margin-top:6px;">
					<input type="checkbox" name="ss_yacht_clear_layout_url" value="1" />
					<?php esc_html_e( 'Remove this auto-fetched URL', 'sailscanner-proposals' ); ?>
				</label>
			</p>
			<?php endif; ?>
		</div>

		<script>
		(function ($) {
			var layoutFrame;
			$('#ss-layout-pick').on('click', function () {
				if (layoutFrame) { layoutFrame.open(); return; }
				layoutFrame = wp.media({
					title: '<?php echo esc_js( __( 'Choose Deck Plan / Layout Image', 'sailscanner-proposals' ) ); ?>',
					button: { text: '<?php echo esc_js( __( 'Use this image', 'sailscanner-proposals' ) ); ?>' },
					multiple: false,
					library: { type: 'image' }
				});
				layoutFrame.on('select', function () {
					var att   = layoutFrame.state().get('selection').first().toJSON();
					var thumb = att.sizes && att.sizes.medium ? att.sizes.medium.url : att.url;
					$('#ss_yacht_layout_image_id').val(att.id);
					$('#ss-layout-img').attr('src', thumb);
					$('#ss-layout-preview').show();
				});
				layoutFrame.open();
			});
			$('#ss-layout-remove').on('click', function () {
				$('#ss_yacht_layout_image_id').val('0');
				$('#ss-layout-img').attr('src', '');
				$('#ss-layout-preview').hide();
			});
		}(jQuery));
		</script>
		<?php
	}

	public static function save_yacht_gallery_meta_box( int $post_id, WP_Post $post ) {
		if ( ! isset( $_POST['ss_yacht_gallery_nonce'] )
			|| ! wp_verify_nonce( sanitize_key( $_POST['ss_yacht_gallery_nonce'] ), 'ss_yacht_gallery_save' )
		) {
			return;
		}
		if ( $post->post_type !== 'ss_proposal_yacht' ) {
			return;
		}
		if ( ! current_user_can( 'edit_post', $post_id ) ) {
			return;
		}
		if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) {
			return;
		}

		$raw = isset( $_POST['ss_yacht_gallery_ids'] ) ? sanitize_text_field( wp_unslash( $_POST['ss_yacht_gallery_ids'] ) ) : '';
		// Sanitise to comma-separated positive integers only.
		$ids = implode( ',', array_filter( array_map( 'absint', explode( ',', $raw ) ) ) );
		update_post_meta( $post_id, 'ss_yacht_gallery_ids', $ids );

		// Optionally clear the auto-fetched images_json.
		if ( ! empty( $_POST['ss_yacht_clear_auto_images'] ) ) {
			delete_post_meta( $post_id, 'images_json' );
		}

		// Layout / deck plan image (media library selection).
		if ( isset( $_POST['ss_yacht_layout_image_id'] ) ) {
			$layout_id = absint( $_POST['ss_yacht_layout_image_id'] );
			update_post_meta( $post_id, 'ss_yacht_layout_image_id', $layout_id );
		}
		if ( ! empty( $_POST['ss_yacht_clear_layout_url'] ) ) {
			delete_post_meta( $post_id, 'layout_image_url' );
		}
	}

	// ── Yacht Details meta box ────────────────────────────────────────────────

	public static function render_yacht_details_meta_box( WP_Post $post ) {
		wp_nonce_field( 'ss_yacht_details_save', 'ss_yacht_details_nonce' );

		// Load existing values.
		$display_name = get_post_meta( $post->ID, 'display_name', true );

		$specs_json = get_post_meta( $post->ID, 'specs_json', true );
		$specs      = [];
		if ( is_string( $specs_json ) ) {
			$dec = json_decode( $specs_json, true );
			if ( is_array( $dec ) ) {
				$specs = $dec;
			}
		}
		// Index specs by label for easy lookup.
		$specs_by_label = [];
		foreach ( $specs as $s ) {
			if ( ! empty( $s['label'] ) ) {
				$specs_by_label[ strtolower( (string) $s['label'] ) ] = (string) ( $s['value'] ?? '' );
			}
		}

		$charter_json = get_post_meta( $post->ID, 'charter_json', true );
		$charter      = [];
		if ( is_string( $charter_json ) ) {
			$dec = json_decode( $charter_json, true );
			if ( is_array( $dec ) ) {
				$charter = $dec;
			}
		}
		// Use top-level charter fields (or first slot when grouped).
		$c_base     = $charter['base']      ?? '';
		$c_to       = $charter['to']        ?? '';
		$c_datefrom = $charter['date_from'] ?? '';
		$c_dateto   = $charter['date_to']   ?? '';
		$c_checkin  = $charter['checkin']   ?? '';
		$c_checkout = $charter['checkout']  ?? '';

		$highlights_json = get_post_meta( $post->ID, 'highlights_json', true );
		$highlights      = [];
		if ( is_string( $highlights_json ) ) {
			$dec = json_decode( $highlights_json, true );
			if ( is_array( $dec ) ) {
				$highlights = $dec;
			}
		}
		$highlights_csv = implode( ', ', $highlights );

		// Helper: render a labelled field row.
		$field = function( $label, $name, $value, $placeholder = '' ) {
			echo '<tr>';
			echo '<th scope="row" style="width:160px;padding:6px 10px 6px 0;font-weight:600;vertical-align:middle;">'
				. esc_html( $label ) . '</th>';
			echo '<td style="padding:4px 0;">'
				. '<input type="text" name="' . esc_attr( $name ) . '" value="' . esc_attr( $value ) . '" '
				. 'placeholder="' . esc_attr( $placeholder ) . '" class="widefat" style="max-width:420px;" />'
				. '</td>';
			echo '</tr>';
		};
		?>
		<style>
		.ss-details-section { margin: 0 0 14px; }
		.ss-details-section h4 { margin: 0 0 6px; font-size: 13px; color: #1e3a5f; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; }
		.ss-details-table { border-collapse: collapse; width: 100%; }
		.ss-details-table th { text-align: left; }
		</style>

		<div class="ss-details-section">
			<h4><?php esc_html_e( 'Display Name', 'sailscanner-proposals' ); ?></h4>
			<table class="ss-details-table">
				<?php $field( __( 'Name', 'sailscanner-proposals' ), 'ss_yd_display_name', $display_name, 'e.g. Bali 5.4' ); ?>
			</table>
		</div>

		<div class="ss-details-section">
			<h4><?php esc_html_e( 'Specifications', 'sailscanner-proposals' ); ?></h4>
			<table class="ss-details-table">
				<?php
				$spec_fields = [
					'Year'       => [ 'ss_yd_spec_year',       'e.g. 2022' ],
					'Type'       => [ 'ss_yd_spec_type',       'e.g. Catamaran (Bali 5.4)' ],
					'Length'     => [ 'ss_yd_spec_length',     'e.g. 16.0 m (52.5 ft)' ],
					'Beam'       => [ 'ss_yd_spec_beam',       'e.g. 8.20 m' ],
					'Draft'      => [ 'ss_yd_spec_draft',      'e.g. 1.30 m' ],
					'Berths'     => [ 'ss_yd_spec_berths',     'e.g. 10' ],
					'Cabins'     => [ 'ss_yd_spec_cabins',     'e.g. 5' ],
					'WC / Shower'=> [ 'ss_yd_spec_wc',        'e.g. 4 (Electric Toilets)' ],
					'Engine'     => [ 'ss_yd_spec_engine',     'e.g. Volvo Penta 2x57hp' ],
					'Mainsail'   => [ 'ss_yd_spec_mainsail',   'e.g. Furling' ],
				];
				foreach ( $spec_fields as $label => [ $name, $ph ] ) {
					$val = $specs_by_label[ strtolower( $label ) ] ?? '';
					$field( $label, $name, $val, $ph );
				}
				?>
			</table>
		</div>

		<div class="ss-details-section">
			<h4><?php esc_html_e( 'Charter Details', 'sailscanner-proposals' ); ?></h4>
			<p style="margin:0 0 8px;font-size:12px;color:#6b7280;"><?php esc_html_e( 'Edits here update the top-level charter slot only. Multi-slot charters are best re-imported.', 'sailscanner-proposals' ); ?></p>
			<table class="ss-details-table">
				<?php
				$field( __( 'Base', 'sailscanner-proposals' ),      'ss_yd_charter_base',     $c_base,     'e.g. Italy, Sardinia / Porto Rotondo' );
				$field( __( 'To', 'sailscanner-proposals' ),        'ss_yd_charter_to',       $c_to,       'e.g. Italy, Sardinia / Porto Rotondo' );
				$field( __( 'Date from', 'sailscanner-proposals' ), 'ss_yd_charter_datefrom', $c_datefrom, 'e.g. 15 August 2026' );
				$field( __( 'Date to', 'sailscanner-proposals' ),   'ss_yd_charter_dateto',   $c_dateto,   'e.g. 22 August 2026' );
				$field( __( 'Check-in', 'sailscanner-proposals' ),  'ss_yd_charter_checkin',  $c_checkin,  'e.g. 18:00' );
				$field( __( 'Check-out', 'sailscanner-proposals' ), 'ss_yd_charter_checkout', $c_checkout, 'e.g. 08:00' );
				?>
			</table>
		</div>

		<div class="ss-details-section">
			<h4><?php esc_html_e( 'Equipment & Features', 'sailscanner-proposals' ); ?></h4>
			<p style="margin:0 0 6px;font-size:12px;color:#6b7280;"><?php esc_html_e( 'Comma-separated list of equipment tags shown as pills.', 'sailscanner-proposals' ); ?></p>
			<textarea name="ss_yd_highlights" class="widefat" rows="4" style="font-size:13px;"><?php echo esc_textarea( $highlights_csv ); ?></textarea>
		</div>
		<?php
	}

	public static function save_yacht_details_meta_box( int $post_id, WP_Post $post ) {
		if ( ! isset( $_POST['ss_yacht_details_nonce'] )
			|| ! wp_verify_nonce( sanitize_key( $_POST['ss_yacht_details_nonce'] ), 'ss_yacht_details_save' )
		) {
			return;
		}
		if ( $post->post_type !== 'ss_proposal_yacht' ) {
			return;
		}
		if ( ! current_user_can( 'edit_post', $post_id ) ) {
			return;
		}
		if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) {
			return;
		}

		// Display name.
		if ( isset( $_POST['ss_yd_display_name'] ) ) {
			update_post_meta( $post_id, 'display_name', sanitize_text_field( wp_unslash( $_POST['ss_yd_display_name'] ) ) );
		}

		// Specs — rebuild specs_json from individual fields.
		$spec_map = [
			'Year'        => 'ss_yd_spec_year',
			'Type'        => 'ss_yd_spec_type',
			'Length'      => 'ss_yd_spec_length',
			'Beam'        => 'ss_yd_spec_beam',
			'Draft'       => 'ss_yd_spec_draft',
			'Berths'      => 'ss_yd_spec_berths',
			'Cabins'      => 'ss_yd_spec_cabins',
			'WC / Shower' => 'ss_yd_spec_wc',
			'Engine'      => 'ss_yd_spec_engine',
			'Mainsail'    => 'ss_yd_spec_mainsail',
		];
		// Preserve any extra specs not covered by the form (e.g. custom ones from import).
		$existing_json = get_post_meta( $post_id, 'specs_json', true );
		$existing_spec = [];
		if ( is_string( $existing_json ) ) {
			$dec = json_decode( $existing_json, true );
			if ( is_array( $dec ) ) {
				$existing_spec = $dec;
			}
		}
		$managed_labels = array_map( 'strtolower', array_keys( $spec_map ) );
		$extra_specs    = array_values( array_filter( $existing_spec, function( $s ) use ( $managed_labels ) {
			return ! in_array( strtolower( (string) ( $s['label'] ?? '' ) ), $managed_labels, true );
		} ) );
		$new_specs = [];
		foreach ( $spec_map as $label => $field_name ) {
			if ( isset( $_POST[ $field_name ] ) ) {
				$val = sanitize_text_field( wp_unslash( $_POST[ $field_name ] ) );
				if ( $val !== '' ) {
					$new_specs[] = [ 'label' => $label, 'value' => $val ];
				}
			}
		}
		update_post_meta( $post_id, 'specs_json', wp_json_encode( array_merge( $new_specs, $extra_specs ), JSON_UNESCAPED_UNICODE ) );

		// Update top-level scalar meta too (used in display shortcuts).
		foreach ( [
			'ss_yd_spec_year'   => 'year',
			'ss_yd_spec_length' => 'length_m',
			'ss_yd_spec_berths' => 'berths',
			'ss_yd_spec_cabins' => 'cabins',
		] as $post_key => $meta_key ) {
			if ( isset( $_POST[ $post_key ] ) ) {
				update_post_meta( $post_id, $meta_key, sanitize_text_field( wp_unslash( $_POST[ $post_key ] ) ) );
			}
		}

		// Charter details — update top-level keys in charter_json.
		$charter_fields = [
			'ss_yd_charter_base'     => 'base',
			'ss_yd_charter_to'       => 'to',
			'ss_yd_charter_datefrom' => 'date_from',
			'ss_yd_charter_dateto'   => 'date_to',
			'ss_yd_charter_checkin'  => 'checkin',
			'ss_yd_charter_checkout' => 'checkout',
		];
		$charter_raw = get_post_meta( $post_id, 'charter_json', true );
		$charter     = [];
		if ( is_string( $charter_raw ) ) {
			$dec = json_decode( $charter_raw, true );
			if ( is_array( $dec ) ) {
				$charter = $dec;
			}
		}
		foreach ( $charter_fields as $post_key => $charter_key ) {
			if ( isset( $_POST[ $post_key ] ) ) {
				$charter[ $charter_key ] = sanitize_text_field( wp_unslash( $_POST[ $post_key ] ) );
			}
		}
		update_post_meta( $post_id, 'charter_json', wp_json_encode( $charter, JSON_UNESCAPED_UNICODE ) );
		// Sync base_name shortcut.
		if ( ! empty( $charter['base'] ) ) {
			update_post_meta( $post_id, 'base_name', sanitize_text_field( $charter['base'] ) );
		}

		// Highlights — parse comma-separated string back to JSON array.
		if ( isset( $_POST['ss_yd_highlights'] ) ) {
			$raw_hl  = sanitize_textarea_field( wp_unslash( $_POST['ss_yd_highlights'] ) );
			$hl_arr  = array_values( array_filter( array_map( 'trim', explode( ',', $raw_hl ) ) ) );
			update_post_meta( $post_id, 'highlights_json', wp_json_encode( $hl_arr, JSON_UNESCAPED_UNICODE ) );
		}
	}

	// ── Pricing meta box ──────────────────────────────────────────────────────

	public static function render_yacht_pricing_meta_box( WP_Post $post ) {
		wp_nonce_field( 'ss_yacht_pricing_save', 'ss_yacht_pricing_nonce' );

		$prices_json = get_post_meta( $post->ID, 'prices_json', true );
		$prices      = [];
		if ( is_string( $prices_json ) ) {
			$dec = json_decode( $prices_json, true );
			if ( is_array( $dec ) ) {
				$prices = $dec;
			}
		}

		$base_price    = $prices['base_price']    ?? '';
		$charter_price = $prices['charter_price'] ?? '';
		$prorated_note = $prices['prorated_note'] ?? '';
		$discounts     = is_array( $prices['discounts'] ?? null )         ? $prices['discounts']         : [];
		$mand_adv      = is_array( $prices['mandatory_advance'] ?? null ) ? $prices['mandatory_advance'] : [];
		$mand_base     = is_array( $prices['mandatory_base'] ?? null )    ? $prices['mandatory_base']    : [];
		$optional      = is_array( $prices['optional_extras'] ?? null )   ? $prices['optional_extras']   : [];

		?>
		<p style="color:#6b7280;font-size:12px;margin:0 0 12px;">
			<?php esc_html_e( 'Edit any price line directly. Use + to add rows, × to remove. Amount format must match existing values (e.g. 1,500.00 €).', 'sailscanner-proposals' ); ?>
		</p>

		<table style="border-collapse:collapse;width:100%;margin-bottom:16px;">
			<tr>
				<th style="text-align:left;width:50%;padding:4px 12px 4px 0;font-size:13px;"><?php esc_html_e( 'Base Price', 'sailscanner-proposals' ); ?></th>
				<td style="padding:4px 0;"><input type="text" name="ss_yp_base_price" value="<?php echo esc_attr( $base_price ); ?>" class="widefat" placeholder="e.g. 15,510.00 €" /></td>
			</tr>
			<tr>
				<th style="text-align:left;padding:4px 12px 4px 0;font-size:13px;"><?php esc_html_e( 'Charter Price (net)', 'sailscanner-proposals' ); ?></th>
				<td style="padding:4px 0;"><input type="text" name="ss_yp_charter_price" value="<?php echo esc_attr( $charter_price ); ?>" class="widefat" placeholder="e.g. 5,584.00 €" /></td>
			</tr>
			<tr>
				<th style="text-align:left;padding:4px 12px 4px 0;font-size:13px;"><?php esc_html_e( 'Pro-rated note', 'sailscanner-proposals' ); ?></th>
				<td style="padding:4px 0;"><input type="text" name="ss_yp_prorated_note" value="<?php echo esc_attr( $prorated_note ); ?>" class="widefat" placeholder="<?php esc_attr_e( 'Leave blank unless price was pro-rated', 'sailscanner-proposals' ); ?>" /></td>
			</tr>
		</table>

		<?php
		$sections = [
			'discounts'         => [ __( 'Discounts', 'sailscanner-proposals' ),         $discounts,  'ss_yp_disc',     false ],
			'mandatory_advance' => [ __( 'Mandatory Extras — Payable in Advance', 'sailscanner-proposals' ), $mand_adv, 'ss_yp_mand_adv', false ],
			'mandatory_base'    => [ __( 'Mandatory Extras — Payable at Base', 'sailscanner-proposals' ),    $mand_base,'ss_yp_mand_base',false ],
			'optional_extras'   => [ __( 'Optional Extras', 'sailscanner-proposals' ),   $optional,   'ss_yp_opt',      true  ],
		];
		foreach ( $sections as $key => [ $heading, $rows, $prefix, $has_note ] ) :
		?>
		<div class="ss-pricing-section" style="margin-bottom:18px;" data-prefix="<?php echo esc_attr( $prefix ); ?>" data-has-note="<?php echo $has_note ? '1' : '0'; ?>">
			<h4 style="margin:0 0 6px;font-size:13px;color:#1e3a5f;border-bottom:1px solid #e5e7eb;padding-bottom:4px;">
				<?php echo esc_html( $heading ); ?>
			</h4>
			<table class="ss-pricing-rows" style="width:100%;border-collapse:collapse;">
				<thead>
					<tr>
						<th style="text-align:left;font-size:12px;color:#6b7280;padding:2px 8px 4px 0;font-weight:400;width:55%;"><?php esc_html_e( 'Item / Label', 'sailscanner-proposals' ); ?></th>
						<th style="text-align:left;font-size:12px;color:#6b7280;padding:2px 8px 4px 0;font-weight:400;width:<?php echo $has_note ? '25%' : '40%'; ?>;"><?php esc_html_e( 'Amount', 'sailscanner-proposals' ); ?></th>
						<?php if ( $has_note ) : ?>
						<th style="text-align:left;font-size:12px;color:#6b7280;padding:2px 8px 4px 0;font-weight:400;width:15%;"><?php esc_html_e( 'Note', 'sailscanner-proposals' ); ?></th>
						<?php endif; ?>
						<th style="width:30px;"></th>
					</tr>
				</thead>
				<tbody>
				<?php foreach ( $rows as $i => $row ) :
					$lbl  = is_array( $row ) ? ( $row['label']  ?? '' ) : (string) $row;
					$amt  = is_array( $row ) ? ( $row['amount'] ?? '' ) : '';
					$note = is_array( $row ) ? ( $row['note']   ?? '' ) : '';
				?>
				<tr class="ss-pricing-row">
					<td style="padding:3px 6px 3px 0;"><input type="text" name="<?php echo esc_attr( $prefix ); ?>_label[]" value="<?php echo esc_attr( $lbl ); ?>" class="widefat" /></td>
					<td style="padding:3px 6px 3px 0;"><input type="text" name="<?php echo esc_attr( $prefix ); ?>_amount[]" value="<?php echo esc_attr( $amt ); ?>" class="widefat" placeholder="e.g. 150.00 €" /></td>
					<?php if ( $has_note ) : ?>
					<td style="padding:3px 6px 3px 0;"><input type="text" name="<?php echo esc_attr( $prefix ); ?>_note[]" value="<?php echo esc_attr( $note ); ?>" class="widefat" placeholder="Requested" /></td>
					<?php endif; ?>
					<td style="padding:3px 0;"><button type="button" class="button-link ss-pricing-remove" style="color:#dc2626;padding:4px;" aria-label="<?php esc_attr_e( 'Remove row', 'sailscanner-proposals' ); ?>">&#x2715;</button></td>
				</tr>
				<?php endforeach; ?>
				</tbody>
			</table>
			<button type="button" class="button ss-pricing-add-row" style="margin-top:6px;font-size:12px;">
				+ <?php esc_html_e( 'Add row', 'sailscanner-proposals' ); ?>
			</button>
		</div>
		<?php endforeach; ?>

		<script>
		(function ($) {
			// Add row.
			$('.ss-pricing-add-row').on('click', function () {
				var $section  = $(this).closest('.ss-pricing-section');
				var prefix    = $section.data('prefix');
				var hasNote   = $section.data('has-note') === 1 || $section.data('has-note') === '1';
				var noteCol   = hasNote
					? '<td style="padding:3px 6px 3px 0;"><input type="text" name="' + prefix + '_note[]" value="" class="widefat" placeholder="Requested" /></td>'
					: '';
				var noteHead  = hasNote ? '<th style="width:15%;"></th>' : '';
				var $row = $(
					'<tr class="ss-pricing-row">' +
					'<td style="padding:3px 6px 3px 0;"><input type="text" name="' + prefix + '_label[]" value="" class="widefat" /></td>' +
					'<td style="padding:3px 6px 3px 0;"><input type="text" name="' + prefix + '_amount[]" value="" class="widefat" placeholder="e.g. 150.00 €" /></td>' +
					noteCol +
					'<td style="padding:3px 0;"><button type="button" class="button-link ss-pricing-remove" style="color:#dc2626;padding:4px;" aria-label="Remove">&#x2715;</button></td>' +
					'</tr>'
				);
				$section.find('.ss-pricing-rows tbody').append($row);
				$row.find('input').first().focus();
			});

			// Remove row.
			$(document).on('click', '.ss-pricing-remove', function () {
				$(this).closest('.ss-pricing-row').remove();
			});
		}(jQuery));
		</script>
		<?php
	}

	public static function save_yacht_pricing_meta_box( int $post_id, WP_Post $post ) {
		if ( ! isset( $_POST['ss_yacht_pricing_nonce'] )
			|| ! wp_verify_nonce( sanitize_key( $_POST['ss_yacht_pricing_nonce'] ), 'ss_yacht_pricing_save' )
		) {
			return;
		}
		if ( $post->post_type !== 'ss_proposal_yacht' ) {
			return;
		}
		if ( ! current_user_can( 'edit_post', $post_id ) ) {
			return;
		}
		if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) {
			return;
		}

		// Load existing prices so we preserve any keys we don't manage (e.g. deposit).
		$existing_json = get_post_meta( $post_id, 'prices_json', true );
		$prices        = [];
		if ( is_string( $existing_json ) ) {
			$dec = json_decode( $existing_json, true );
			if ( is_array( $dec ) ) {
				$prices = $dec;
			}
		}

		// Scalar fields.
		foreach ( [
			'ss_yp_base_price'    => 'base_price',
			'ss_yp_charter_price' => 'charter_price',
			'ss_yp_prorated_note' => 'prorated_note',
		] as $post_key => $prices_key ) {
			if ( isset( $_POST[ $post_key ] ) ) {
				$val = sanitize_text_field( wp_unslash( $_POST[ $post_key ] ) );
				if ( $val !== '' ) {
					$prices[ $prices_key ] = $val;
				} else {
					unset( $prices[ $prices_key ] );
				}
			}
		}

		// Row sections (label + amount [+ note]).
		$row_sections = [
			'discounts'         => [ 'ss_yp_disc',      false ],
			'mandatory_advance' => [ 'ss_yp_mand_adv',  false ],
			'mandatory_base'    => [ 'ss_yp_mand_base', false ],
			'optional_extras'   => [ 'ss_yp_opt',       true  ],
		];
		foreach ( $row_sections as $prices_key => [ $prefix, $has_note ] ) {
			$labels  = isset( $_POST[ $prefix . '_label' ] )  ? (array) wp_unslash( $_POST[ $prefix . '_label' ] )  : [];
			$amounts = isset( $_POST[ $prefix . '_amount' ] ) ? (array) wp_unslash( $_POST[ $prefix . '_amount' ] ) : [];
			$notes   = $has_note && isset( $_POST[ $prefix . '_note' ] ) ? (array) wp_unslash( $_POST[ $prefix . '_note' ] ) : [];

			$rows = [];
			foreach ( $labels as $i => $lbl ) {
				$lbl = sanitize_text_field( $lbl );
				$amt = sanitize_text_field( $amounts[ $i ] ?? '' );
				if ( $lbl === '' && $amt === '' ) {
					continue; // Skip blank rows.
				}
				$row = [ 'label' => $lbl, 'amount' => $amt ];
				if ( $has_note ) {
					$note = sanitize_text_field( $notes[ $i ] ?? '' );
					if ( $note !== '' ) {
						$row['note'] = $note;
					}
				}
				$rows[] = $row;
			}
			if ( ! empty( $rows ) ) {
				$prices[ $prices_key ] = $rows;
			} else {
				unset( $prices[ $prices_key ] );
			}
		}

		update_post_meta( $post_id, 'prices_json', wp_json_encode( $prices, JSON_UNESCAPED_UNICODE ) );
	}

	/**
	 * Render the Requirements meta box.
	 *
	 * Pre-populates each field from the override (ss_answers_override) when set,
	 * otherwise falls back to the original ss_lead_json answers so the form always
	 * shows the current effective value.
	 *
	 * @param WP_Post $post
	 */
	public static function render_requirements_meta_box( $post ) {
		wp_nonce_field( 'ss_req_meta_nonce', 'ss_req_meta_nonce' );

		// Read original lead answers.
		$lead    = [];
		$lead_json = get_post_meta( $post->ID, 'ss_lead_json', true );
		if ( is_string( $lead_json ) ) {
			$dec = json_decode( $lead_json, true );
			if ( is_array( $dec ) ) {
				$lead = $dec;
			}
		}
		$orig = isset( $lead['answers'] ) && is_array( $lead['answers'] ) ? $lead['answers'] : [];

		// Read any existing overrides.
		$override = [];
		$override_json = get_post_meta( $post->ID, 'ss_answers_override', true );
		if ( is_string( $override_json ) && $override_json !== '' ) {
			$dec = json_decode( $override_json, true );
			if ( is_array( $dec ) ) {
				$override = $dec;
			}
		}

		// Helper: returns the effective value (override first, then original lead).
		$eff = function( $key ) use ( $orig, $override ) {
			if ( isset( $override[ $key ] ) && $override[ $key ] !== '' ) {
				return (string) $override[ $key ];
			}
			if ( isset( $orig[ $key ] ) ) {
				$v = $orig[ $key ];
				return is_array( $v ) ? implode( ', ', $v ) : (string) $v;
			}
			return '';
		};

		// Dates are nested: answers.dates.start / answers.dates.end.
		$dates_start = isset( $override['dates']['start'] ) && $override['dates']['start'] !== ''
			? $override['dates']['start']
			: ( $orig['dates']['start'] ?? '' );
		$dates_end   = isset( $override['dates']['end'] ) && $override['dates']['end'] !== ''
			? $override['dates']['end']
			: ( $orig['dates']['end'] ?? '' );

		$fields = [
			[ 'key' => '_dates_start',   'label' => 'Start date',   'value' => $dates_start,          'type' => 'date' ],
			[ 'key' => '_dates_end',     'label' => 'End date',     'value' => $dates_end,             'type' => 'date' ],
			[ 'key' => 'charterType',    'label' => 'Charter type', 'value' => $eff('charterType'),    'type' => 'text' ],
			[ 'key' => 'boatType',       'label' => 'Boat type',    'value' => $eff('boatType'),       'type' => 'text' ],
			[ 'key' => 'country',        'label' => 'Country',      'value' => $eff('country'),        'type' => 'text' ],
			[ 'key' => 'region',         'label' => 'Region',       'value' => $eff('region'),         'type' => 'text' ],
			[ 'key' => 'size',           'label' => 'Size (ft)',    'value' => $eff('size'),           'type' => 'text' ],
			[ 'key' => 'cabins',         'label' => 'Cabins',       'value' => $eff('cabins'),         'type' => 'text' ],
			[ 'key' => 'budget',         'label' => 'Budget',       'value' => $eff('budget'),         'type' => 'text' ],
			[ 'key' => 'experienceLevel','label' => 'Experience',   'value' => $eff('experienceLevel'),'type' => 'text' ],
		];
		?>
		<style>
			#ss_proposal_requirements .ss-req-grid {
				display: grid;
				grid-template-columns: 1fr 1fr;
				gap: 10px 24px;
				margin-top: 8px;
			}
			#ss_proposal_requirements .ss-req-field label {
				display: block;
				font-weight: 600;
				font-size: 11px;
				color: #666;
				margin-bottom: 3px;
				text-transform: uppercase;
				letter-spacing: .04em;
			}
			#ss_proposal_requirements .ss-req-field input {
				width: 100%;
				box-sizing: border-box;
			}
			#ss_proposal_requirements .ss-req-note {
				color: #888;
				font-size: 12px;
				margin: 10px 0 0;
				font-style: italic;
			}
		</style>
		<div class="ss-req-grid">
			<?php foreach ( $fields as $f ) : ?>
			<div class="ss-req-field">
				<label for="ss_req_<?php echo esc_attr( $f['key'] ); ?>"><?php echo esc_html( $f['label'] ); ?></label>
				<input
					type="<?php echo esc_attr( $f['type'] ); ?>"
					id="ss_req_<?php echo esc_attr( $f['key'] ); ?>"
					name="ss_req[<?php echo esc_attr( $f['key'] ); ?>]"
					value="<?php echo esc_attr( $f['value'] ); ?>"
					class="widefat"
				/>
			</div>
			<?php endforeach; ?>
		</div>
		<p class="ss-req-note">
			Values shown are the current effective values (your edits override the original lead data). Clear a field to revert it to the original. The original lead data is never modified.
		</p>
		<?php
	}

	/**
	 * Save the requirements meta box. Stores non-empty values in ss_answers_override.
	 * Deletes the meta entirely if everything is cleared (reverts to original lead data).
	 *
	 * @param int     $post_id
	 * @param WP_Post $post
	 */
	public static function save_requirements_meta_box( $post_id, $post ) {
		if (
			! isset( $_POST['ss_req_meta_nonce'] ) ||
			! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['ss_req_meta_nonce'] ) ), 'ss_req_meta_nonce' ) ||
			( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) ||
			! current_user_can( 'edit_post', $post_id ) ||
			$post->post_type !== 'ss_proposal'
		) {
			return;
		}

		$raw = isset( $_POST['ss_req'] ) && is_array( $_POST['ss_req'] ) ? $_POST['ss_req'] : [];

		$override  = [];
		$flat_keys = [ 'charterType', 'boatType', 'country', 'region', 'size', 'cabins', 'budget', 'experienceLevel' ];
		foreach ( $flat_keys as $k ) {
			$v = isset( $raw[ $k ] ) ? sanitize_text_field( wp_unslash( (string) $raw[ $k ] ) ) : '';
			if ( $v !== '' ) {
				$override[ $k ] = $v;
			}
		}

		// Dates stored nested: dates => [ start => ..., end => ... ].
		$dates_start = isset( $raw['_dates_start'] ) ? sanitize_text_field( wp_unslash( (string) $raw['_dates_start'] ) ) : '';
		$dates_end   = isset( $raw['_dates_end'] )   ? sanitize_text_field( wp_unslash( (string) $raw['_dates_end'] ) )   : '';
		if ( $dates_start !== '' || $dates_end !== '' ) {
			$override['dates'] = [];
			if ( $dates_start !== '' ) {
				$override['dates']['start'] = $dates_start;
			}
			if ( $dates_end !== '' ) {
				$override['dates']['end'] = $dates_end;
			}
		}

		if ( ! empty( $override ) ) {
			update_post_meta( $post_id, 'ss_answers_override', wp_json_encode( $override, JSON_UNESCAPED_UNICODE ) );
		} else {
			// All fields cleared — remove override so original lead data shows again.
			delete_post_meta( $post_id, 'ss_answers_override' );
		}
	}

	// ── Itinerary meta box ────────────────────────────────────────────────────

	/**
	 * Render the "Example Itinerary" meta box.
	 * Shows a URL field; saving auto-populates title/image/excerpt/days/distance from the WP post.
	 *
	 * @param WP_Post $post
	 */
	public static function render_itinerary_meta_box( $post ) {
		wp_nonce_field( 'ss_itin_meta_nonce', 'ss_itin_meta_nonce' );

		$url     = get_post_meta( $post->ID, 'ss_itinerary_link_url',      true );
		$title   = get_post_meta( $post->ID, 'ss_itinerary_link_title',    true );
		$image   = get_post_meta( $post->ID, 'ss_itinerary_link_image',    true );
		$days    = get_post_meta( $post->ID, 'ss_itinerary_link_days',     true );
		$dist    = get_post_meta( $post->ID, 'ss_itinerary_link_distance', true );
		$region  = get_post_meta( $post->ID, 'ss_itinerary_link_region',   true );
		$summary = get_post_meta( $post->ID, 'ss_itinerary_link_summary',  true );
		?>
		<style>
			#ss_proposal_itinerary .ss-itin-row { margin-bottom: 10px; }
			#ss_proposal_itinerary .ss-itin-row label { display: block; font-weight: 600; font-size: 11px; color: #666; margin-bottom: 3px; text-transform: uppercase; letter-spacing: .04em; }
			#ss_proposal_itinerary .ss-itin-row input, #ss_proposal_itinerary .ss-itin-row textarea { width: 100%; box-sizing: border-box; }
			#ss_proposal_itinerary .ss-itin-preview { display: flex; gap: 12px; align-items: flex-start; margin-top: 12px; padding: 10px; background: #f8f9fa; border-radius: 6px; }
			#ss_proposal_itinerary .ss-itin-preview img { width: 80px; height: 55px; object-fit: cover; border-radius: 4px; flex-shrink: 0; }
			#ss_proposal_itinerary .ss-itin-preview-text { font-size: 12px; color: #444; }
			#ss_proposal_itinerary .ss-itin-preview-text strong { display: block; color: #12305c; margin-bottom: 2px; }
			#ss_proposal_itinerary .ss-itin-meta-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px 16px; }
			#ss_proposal_itinerary .ss-itin-note { color: #888; font-size: 12px; margin: 8px 0 0; font-style: italic; }
		</style>

		<div class="ss-itin-row">
			<label for="ss_itin_url">Itinerary URL (SailScanner itinerary page URL)</label>
			<input type="url" id="ss_itin_url" name="ss_itin_url"
				value="<?php echo esc_attr( $url ); ?>"
				placeholder="https://sailscanner.ai/itinerary/your-itinerary-slug/"
				class="widefat" />
			<p class="ss-itin-note">Paste the SailScanner itinerary URL and save — title, image and description will be fetched automatically.</p>
		</div>

		<?php if ( $url && ( $title || $image ) ) : ?>
		<div class="ss-itin-preview">
			<?php if ( $image ) : ?>
			<img src="<?php echo esc_url( $image ); ?>" alt="" />
			<?php endif; ?>
			<div class="ss-itin-preview-text">
				<?php if ( $title ) : ?><strong><?php echo esc_html( $title ); ?></strong><?php endif; ?>
				<?php if ( $days || $dist || $region ) : ?>
				<span>
					<?php if ( $days ) echo esc_html( $days ) . ' days'; ?>
					<?php if ( $dist ) echo ' · ' . esc_html( $dist ); ?>
					<?php if ( $region ) echo ' · ' . esc_html( $region ); ?>
				</span>
				<?php endif; ?>
			</div>
		</div>
		<?php endif; ?>

		<p class="ss-itin-note" style="margin-top:12px;">Override fetched values (leave blank to use auto-fetched):</p>
		<div class="ss-itin-meta-grid" style="margin-top:6px;">
			<div class="ss-itin-row">
				<label for="ss_itin_days">Days</label>
				<input type="text" id="ss_itin_days" name="ss_itin_days" value="<?php echo esc_attr( $days ); ?>" placeholder="e.g. 7" class="widefat" />
			</div>
			<div class="ss-itin-row">
				<label for="ss_itin_distance">Distance</label>
				<input type="text" id="ss_itin_distance" name="ss_itin_distance" value="<?php echo esc_attr( $dist ); ?>" placeholder="e.g. 90 NM" class="widefat" />
			</div>
			<div class="ss-itin-row">
				<label for="ss_itin_region">Region / tag</label>
				<input type="text" id="ss_itin_region" name="ss_itin_region" value="<?php echo esc_attr( $region ); ?>" placeholder="e.g. Sardinia" class="widefat" />
			</div>
		</div>
		<div class="ss-itin-row" style="margin-top:8px;">
			<label for="ss_itin_summary">Description (override)</label>
			<textarea id="ss_itin_summary" name="ss_itin_summary" rows="3" class="widefat"><?php echo esc_textarea( $summary ); ?></textarea>
		</div>
		<?php
	}

	/**
	 * Save the itinerary meta box.
	 * When the URL is new or changed, auto-fetches title/image/excerpt/meta from the linked WP post.
	 * Manual override fields take priority over auto-fetched values.
	 *
	 * @param int     $post_id
	 * @param WP_Post $post
	 */
	public static function save_itinerary_meta_box( $post_id, $post ) {
		if (
			! isset( $_POST['ss_itin_meta_nonce'] ) ||
			! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['ss_itin_meta_nonce'] ) ), 'ss_itin_meta_nonce' ) ||
			( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) ||
			! current_user_can( 'edit_post', $post_id ) ||
			$post->post_type !== 'ss_proposal'
		) {
			return;
		}

		$new_url = isset( $_POST['ss_itin_url'] ) ? esc_url_raw( wp_unslash( $_POST['ss_itin_url'] ) ) : '';
		$old_url = get_post_meta( $post_id, 'ss_itinerary_link_url', true );

		// Clear everything if URL was removed.
		if ( $new_url === '' ) {
			foreach ( [ 'ss_itinerary_link_url', 'ss_itinerary_link_title', 'ss_itinerary_link_image',
				'ss_itinerary_link_summary', 'ss_itinerary_link_days', 'ss_itinerary_link_distance',
				'ss_itinerary_link_region' ] as $k ) {
				delete_post_meta( $post_id, $k );
			}
			return;
		}

		update_post_meta( $post_id, 'ss_itinerary_link_url', $new_url );

		// Auto-fetch from same-site WP post when URL is new or changed.
		if ( $new_url !== $old_url ) {
			$itin_post_id = url_to_postid( $new_url );
			if ( $itin_post_id ) {
				$fetched_title   = get_the_title( $itin_post_id );
				$fetched_excerpt = get_the_excerpt( $itin_post_id );
				$fetched_image   = get_the_post_thumbnail_url( $itin_post_id, 'large' );
				if ( ! $fetched_image ) {
					$fetched_image = get_the_post_thumbnail_url( $itin_post_id, 'full' );
				}

				// Try common naming conventions for days/distance/region on the itinerary post.
				$fetched_days = '';
				foreach ( [ 'days', '_ss_days', 'duration_days', '_duration_days', 'sail_days', 'ss_days', '_days' ] as $k ) {
					$v = get_post_meta( $itin_post_id, $k, true );
					if ( $v ) { $fetched_days = (string) $v; break; }
				}
				$fetched_dist = '';
				foreach ( [ 'distance_nm', '_ss_distance_nm', 'total_nm', '_total_nm', 'distance', '_distance', 'ss_distance_nm' ] as $k ) {
					$v = get_post_meta( $itin_post_id, $k, true );
					if ( $v ) { $fetched_dist = (string) $v . ( strpos( (string) $v, 'NM' ) === false ? ' NM' : '' ); break; }
				}
				$fetched_region = '';
				foreach ( [ 'region', '_ss_region', '_region', 'destination_region', 'ss_region', 'area' ] as $k ) {
					$v = get_post_meta( $itin_post_id, $k, true );
					if ( $v ) { $fetched_region = (string) $v; break; }
				}
				// Fallback: try the first assigned category/tag name as region.
				if ( ! $fetched_region ) {
					$terms = get_the_terms( $itin_post_id, 'itinerary_region' ) ?: get_the_terms( $itin_post_id, 'destination' ) ?: get_the_terms( $itin_post_id, 'category' );
					if ( $terms && ! is_wp_error( $terms ) ) {
						$fetched_region = $terms[0]->name;
					}
				}

				if ( $fetched_title )   update_post_meta( $post_id, 'ss_itinerary_link_title',   sanitize_text_field( $fetched_title ) );
				if ( $fetched_excerpt ) update_post_meta( $post_id, 'ss_itinerary_link_summary',  sanitize_textarea_field( $fetched_excerpt ) );
				if ( $fetched_image )   update_post_meta( $post_id, 'ss_itinerary_link_image',    esc_url_raw( $fetched_image ) );
				if ( $fetched_days )    update_post_meta( $post_id, 'ss_itinerary_link_days',     sanitize_text_field( $fetched_days ) );
				if ( $fetched_dist )    update_post_meta( $post_id, 'ss_itinerary_link_distance', sanitize_text_field( $fetched_dist ) );
				if ( $fetched_region )  update_post_meta( $post_id, 'ss_itinerary_link_region',   sanitize_text_field( $fetched_region ) );
			}
		}

		// Apply manual overrides (non-empty fields take priority over auto-fetched values).
		$manual_days    = isset( $_POST['ss_itin_days'] )     ? sanitize_text_field( wp_unslash( $_POST['ss_itin_days'] ) )     : '';
		$manual_dist    = isset( $_POST['ss_itin_distance'] ) ? sanitize_text_field( wp_unslash( $_POST['ss_itin_distance'] ) ) : '';
		$manual_region  = isset( $_POST['ss_itin_region'] )   ? sanitize_text_field( wp_unslash( $_POST['ss_itin_region'] ) )   : '';
		$manual_summary = isset( $_POST['ss_itin_summary'] )  ? sanitize_textarea_field( wp_unslash( $_POST['ss_itin_summary'] ) ) : '';

		if ( $manual_days !== '' )    update_post_meta( $post_id, 'ss_itinerary_link_days',     $manual_days );
		if ( $manual_dist !== '' )    update_post_meta( $post_id, 'ss_itinerary_link_distance', $manual_dist );
		if ( $manual_region !== '' )  update_post_meta( $post_id, 'ss_itinerary_link_region',   $manual_region );
		if ( $manual_summary !== '' ) update_post_meta( $post_id, 'ss_itinerary_link_summary',  $manual_summary );
	}
}
