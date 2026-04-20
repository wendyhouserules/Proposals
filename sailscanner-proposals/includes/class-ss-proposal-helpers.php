<?php
/**
 * Template helpers: yacht display data (never expose source_more_info_url or provider names).
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class SS_Proposal_Helpers {

	/**
	 * Get yacht data safe for front-end (no source URLs or provider names).
	 *
	 * @param int $yacht_id ss_proposal_yacht post ID
	 * @return array display_name, url (SailScanner page), image_url, images (array), specs, highlights, etc.
	 */
	public static function get_yacht_display_data( $yacht_id ) {
		$id = (int) $yacht_id;
		if ( ! $id ) {
			return [];
		}
		$post = get_post( $id );
		if ( ! $post || $post->post_type !== 'ss_proposal_yacht' ) {
			return [];
		}

		$display_name = self::decode_display_string( get_post_meta( $id, 'display_name', true ) ?: get_the_title( $id ) );

		// Media library gallery images (admin-selected) take precedence.
		$gallery_ids_raw = get_post_meta( $id, 'ss_yacht_gallery_ids', true );
		$images          = [];
		if ( is_string( $gallery_ids_raw ) && $gallery_ids_raw !== '' ) {
			foreach ( array_filter( array_map( 'absint', explode( ',', $gallery_ids_raw ) ) ) as $att_id ) {
				$full = wp_get_attachment_image_url( $att_id, 'full' );
				if ( $full ) {
					$images[] = esc_url( $full );
				}
			}
		}

		$images_json = get_post_meta( $id, 'images_json', true );
		if ( is_string( $images_json ) ) {
			$dec = json_decode( $images_json, true );
			if ( is_array( $dec ) ) {
				foreach ( $dec as $item ) {
					if ( is_array( $item ) && ! empty( $item['url'] ) && filter_var( $item['url'], FILTER_VALIDATE_URL ) ) {
						$images[] = esc_url( $item['url'] );
					} elseif ( is_string( $item ) && filter_var( $item, FILTER_VALIDATE_URL ) ) {
						$images[] = esc_url( $item );
					}
				}
			}
		}
		$image_url = self::pick_best_yacht_image( $images );

		$highlights_json = get_post_meta( $id, 'highlights_json', true );
		$highlights       = [];
		if ( is_string( $highlights_json ) ) {
			$dec = json_decode( $highlights_json, true );
			if ( is_array( $dec ) ) {
				$highlights = array_values( array_filter( array_map( 'sanitize_text_field', $dec ) ) );
			}
		}

		$specs_json = get_post_meta( $id, 'specs_json', true );
		$specs      = [];
		if ( is_string( $specs_json ) ) {
			$dec = json_decode( $specs_json, true );
			if ( is_array( $dec ) ) {
				foreach ( $dec as $row ) {
					if ( is_array( $row ) && isset( $row['label'] ) && (string) $row['label'] !== '' ) {
						$specs[] = [
							'label' => sanitize_text_field( (string) $row['label'] ),
							'value' => isset( $row['value'] ) ? sanitize_text_field( (string) $row['value'] ) : '',
						];
					}
				}
			}
		}

		$prices_json = get_post_meta( $id, 'prices_json', true );
		$prices      = [];
		if ( is_string( $prices_json ) ) {
			$dec = json_decode( $prices_json, true );
			if ( is_array( $dec ) ) {
				$prices = $dec;
			}
		}

		$charter_json = get_post_meta( $id, 'charter_json', true );
		$charter      = [];
		if ( is_string( $charter_json ) ) {
			$dec = json_decode( $charter_json, true );
			if ( is_array( $dec ) ) {
				$charter = $dec;
			}
		}

		// Layout image: media library selection takes priority over auto-fetched URL.
		$layout_att_id = (int) get_post_meta( $id, 'ss_yacht_layout_image_id', true );
		if ( $layout_att_id ) {
			$layout_image_url = esc_url( wp_get_attachment_image_url( $layout_att_id, 'full' ) ?: '' );
		} else {
			$raw_layout = get_post_meta( $id, 'layout_image_url', true );
			$layout_image_url = ( is_string( $raw_layout ) && filter_var( $raw_layout, FILTER_VALIDATE_URL ) )
				? esc_url( $raw_layout ) : '';
		}

		return [
			'id'               => $id,
			'display_name'     => $display_name,
			'url'              => get_permalink( $id ),
			'image_url'        => $image_url,
			'images'           => $images,
			'layout_image_url' => $layout_image_url,
			'highlights'       => $highlights,
			'specs'            => $specs,
			'prices'           => $prices,
			'charter'          => $charter,
			'cabins'           => (int) get_post_meta( $id, 'cabins', true ),
			'berths'           => (int) get_post_meta( $id, 'berths', true ),
			'length_m'         => get_post_meta( $id, 'length_m', true ),
			'year'             => (int) get_post_meta( $id, 'year', true ),
			'base_name'        => self::decode_display_string( get_post_meta( $id, 'base_name', true ) ),
			'country'          => get_post_meta( $id, 'country', true ),
			'region'           => get_post_meta( $id, 'region', true ),
			'model'            => get_post_meta( $id, 'model', true ),
		];
	}

	/**
	 * Render charter details (base, dates, times) as HTML.
	 *
	 * Handles two formats:
	 *  - Single slot (legacy): charter_json with top-level base/date_from/date_to/checkin/checkout keys.
	 *  - Multi-slot (merged dedup): charter_json with a 'slots' array, each entry having the above keys.
	 *    When multiple distinct slots exist (same boat at different bases/dates) they are rendered as a
	 *    compact table so the client can see all options at a glance.
	 *
	 * @param array $charter Decoded charter_json array.
	 * @return string Safe HTML, empty string when nothing to show.
	 */
	public static function render_charter_slots( array $charter ): string {
		if ( empty( $charter ) ) {
			return '';
		}

		$slots = ( ! empty( $charter['slots'] ) && is_array( $charter['slots'] ) ) ? array_values( $charter['slots'] ) : null;

		// Deduplicate slots by base + date_from + date_to fingerprint.
		if ( $slots ) {
			$seen_fp = [];
			$unique  = [];
			foreach ( $slots as $slot ) {
				$fp = ( $slot['base'] ?? '' ) . '|' . ( $slot['date_from'] ?? '' ) . '|' . ( $slot['date_to'] ?? '' );
				if ( ! isset( $seen_fp[ $fp ] ) ) {
					$seen_fp[ $fp ] = true;
					$unique[]       = $slot;
				}
			}
			$slots = $unique;
		}

		// Multi-slot: render an availability table.
		if ( $slots && count( $slots ) > 1 ) {
			ob_start();
			?>
			<table class="ss-charter-slots-table">
				<thead>
					<tr>
						<th class="ss-cst-base"><?php esc_html_e( 'Base', 'sailscanner-proposals' ); ?></th>
						<th class="ss-cst-dates"><?php esc_html_e( 'Dates', 'sailscanner-proposals' ); ?></th>
					</tr>
				</thead>
				<tbody>
					<?php foreach ( $slots as $slot ) : ?>
					<?php
					$base       = ! empty( $slot['base'] ) ? sanitize_text_field( (string) $slot['base'] ) : '—';
					$date_parts = [];
					if ( ! empty( $slot['date_from'] ) ) {
						$from_bits    = array_filter( [ $slot['date_from'], $slot['checkin'] ?? '' ] );
						$date_parts[] = implode( ', ', $from_bits );
					}
					if ( ! empty( $slot['date_to'] ) ) {
						$to_bits      = array_filter( [ $slot['date_to'], $slot['checkout'] ?? '' ] );
						$date_parts[] = implode( ', ', $to_bits );
					}
					$dates = ! empty( $date_parts ) ? implode( ' → ', $date_parts ) : '—';
					?>
					<tr>
						<td><?php echo esc_html( $base ); ?></td>
						<td><?php echo esc_html( $dates ); ?></td>
					</tr>
					<?php endforeach; ?>
				</tbody>
			</table>
			<?php
			return ob_get_clean();
		}

		// Single slot (one slot entry or legacy top-level keys).
		$data = ( $slots && count( $slots ) === 1 ) ? $slots[0] : $charter;

		$date_parts = [];
		if ( ! empty( $data['date_from'] ) ) {
			$from_bits    = array_filter( [ $data['date_from'], $data['checkin'] ?? '' ] );
			$date_parts[] = implode( ', ', $from_bits );
		}
		if ( ! empty( $data['date_to'] ) ) {
			$to_bits      = array_filter( [ $data['date_to'], $data['checkout'] ?? '' ] );
			$date_parts[] = implode( ', ', $to_bits );
		}
		$has_base  = ! empty( $data['base'] );
		$has_dates = ! empty( $date_parts );
		if ( ! $has_base && ! $has_dates ) {
			return '';
		}

		ob_start();
		?>
		<div class="ss-proposal-yacht-charter-details">
			<?php if ( $has_base ) : ?>
			<div class="ss-proposal-yacht-charter-row">
				<span class="ss-proposal-yacht-charter-label"><?php esc_html_e( 'Base', 'sailscanner-proposals' ); ?></span>
				<span class="ss-proposal-yacht-charter-value"><?php echo esc_html( sanitize_text_field( (string) $data['base'] ) ); ?></span>
			</div>
			<?php endif; ?>
			<?php if ( $has_dates ) : ?>
			<div class="ss-proposal-yacht-charter-row">
				<span class="ss-proposal-yacht-charter-label"><?php esc_html_e( 'Dates', 'sailscanner-proposals' ); ?></span>
				<span class="ss-proposal-yacht-charter-value"><?php echo esc_html( implode( ' → ', $date_parts ) ); ?></span>
			</div>
			<?php endif; ?>
		</div>
		<?php
		return ob_get_clean();
	}

	/**
	 * Normalize a yacht data item (from ss_yacht_data JSON) to same shape as get_yacht_display_data.
	 * Used when proposal has no ss_proposal_yacht IDs yet (fallback from raw ss_yacht_data).
	 *
	 * @param array $item Raw item (display_name, images_json, highlights_json, cabins, berths, etc.)
	 * @param int   $index Optional index for id when no post exists.
	 * @return array Same keys as get_yacht_display_data; url = '#' when no post.
	 */
	public static function normalize_yacht_data_item( $item, $index = 0 ) {
		if ( ! is_array( $item ) ) {
			return [];
		}
		$display_name = isset( $item['display_name'] ) ? sanitize_text_field( (string) $item['display_name'] ) : '';
		$images       = [];
		$raw          = isset( $item['images_json'] ) ? $item['images_json'] : [];
		if ( is_string( $raw ) ) {
			$dec = json_decode( $raw, true );
			$raw = is_array( $dec ) ? $dec : [];
		}
		foreach ( (array) $raw as $img ) {
			if ( is_string( $img ) && filter_var( $img, FILTER_VALIDATE_URL ) ) {
				$images[] = esc_url( $img );
			} elseif ( is_array( $img ) && ! empty( $img['url'] ) && filter_var( $img['url'], FILTER_VALIDATE_URL ) ) {
				$images[] = esc_url( $img['url'] );
			}
		}
		$image_url = self::pick_best_yacht_image( $images );
		$highlights = [];
		$raw_h      = isset( $item['highlights_json'] ) ? $item['highlights_json'] : [];
		if ( is_string( $raw_h ) ) {
			$dec = json_decode( $raw_h, true );
			$raw_h = is_array( $dec ) ? $dec : [];
		}
		if ( is_array( $raw_h ) ) {
			$highlights = array_values( array_filter( array_map( 'sanitize_text_field', $raw_h ) ) );
		}
		$specs  = [];
		$raw_s  = isset( $item['specs_json'] ) ? $item['specs_json'] : [];
		if ( is_array( $raw_s ) ) {
			foreach ( $raw_s as $row ) {
				if ( is_array( $row ) && isset( $row['label'] ) && (string) $row['label'] !== '' ) {
					$specs[] = [
						'label' => sanitize_text_field( (string) $row['label'] ),
						'value' => isset( $row['value'] ) ? sanitize_text_field( (string) $row['value'] ) : '',
					];
				}
			}
		}
		$prices  = is_array( $item['prices_json'] ?? null ) ? ( $item['prices_json'] ?? [] ) : [];
		$charter = is_array( $item['charter_json'] ?? null ) ? ( $item['charter_json'] ?? [] ) : [];
		$display_name = self::decode_display_string( $display_name ?: __( 'Yacht', 'sailscanner-proposals' ) );
		$base_name    = self::decode_display_string( isset( $item['base_name'] ) ? sanitize_text_field( (string) $item['base_name'] ) : '' );

		return [
			'id'           => $index,
			'display_name' => $display_name ?: __( 'Yacht', 'sailscanner-proposals' ),
			'url'          => '#',
			'image_url'    => $image_url,
			'images'       => $images,
			'highlights'   => $highlights,
			'specs'        => $specs,
			'prices'       => $prices,
			'charter'      => $charter,
			'cabins'       => isset( $item['cabins'] ) ? absint( $item['cabins'] ) : 0,
			'berths'       => isset( $item['berths'] ) ? absint( $item['berths'] ) : 0,
			'length_m'     => isset( $item['length_m'] ) ? $item['length_m'] : '',
			'year'         => isset( $item['year'] ) ? absint( $item['year'] ) : 0,
			'base_name'    => $base_name,
			'country'      => isset( $item['country'] ) ? sanitize_text_field( (string) $item['country'] ) : '',
			'region'       => isset( $item['region'] ) ? sanitize_text_field( (string) $item['region'] ) : '',
			'model'        => isset( $item['model'] ) ? sanitize_text_field( (string) $item['model'] ) : '',
		];
	}

	/**
	 * Determine whether an image URL is a real yacht photo (not a generic MMK placeholder).
	 *
	 * MMK serves all images through a CDN endpoint: documents/image.jpg?name=REALFILE.jpg&width=310
	 * A placeholder has no useful name param (empty, "image.jpg", or "noimage.jpg").
	 * Non-MMK URLs are always accepted.
	 *
	 * @param string $url Image URL to test.
	 * @return bool True if the URL points to a real image.
	 */
	public static function is_real_yacht_image( $url ) {
		if ( ! is_string( $url ) || $url === '' ) {
			return false;
		}
		if ( strpos( $url, 'image.jpg' ) === false ) {
			return true; // Not an MMK CDN URL — assume valid.
		}
		// MMK CDN pattern: .../image.jpg?name=REAL_FILENAME&width=310
		// A placeholder has no name param or a generic name.
		$query = wp_parse_url( $url, PHP_URL_QUERY );
		if ( ! $query ) {
			return false; // Bare image.jpg with no query string → generic placeholder.
		}
		$qs   = [];
		wp_parse_str( $query, $qs );
		$name = isset( $qs['name'] ) ? (string) $qs['name'] : '';
		if ( $name === '' || $name === 'image.jpg' || $name === 'noimage.jpg' ) {
			return false;
		}
		return true;
	}

	/**
	 * Prefer first real image URL from the list; fall back to first URL in list if none qualifies.
	 *
	 * @param array $images Array of image URLs.
	 * @return string Single URL or empty string.
	 */
	public static function pick_best_yacht_image( $images ) {
		if ( empty( $images ) || ! is_array( $images ) ) {
			return '';
		}
		foreach ( $images as $url ) {
			if ( self::is_real_yacht_image( $url ) ) {
				return $url;
			}
		}
		// All URLs failed the check — return first one as last resort.
		return ! empty( $images[0] ) ? (string) $images[0] : '';
	}

	/**
	 * Decode JSON unicode escapes in display strings (e.g. \u00e0 -> à) so they render correctly.
	 *
	 * @param string $s Raw string possibly with \uXXXX.
	 * @return string Decoded string.
	 */
	public static function decode_display_string( $s ) {
		if ( ! is_string( $s ) || $s === '' ) {
			return $s;
		}
		if ( strpos( $s, '\\u' ) === false ) {
			return $s;
		}
		return (string) preg_replace_callback( '/\\\\u([0-9a-fA-F]{4})/', function ( $m ) {
			return mb_convert_encoding( pack( 'H*', $m[1] ), 'UTF-8', 'UCS-2BE' );
		}, $s );
	}

	/**
	 * Extract the contact sub-array from a lead payload.
	 *
	 * Supports two lead shapes:
	 *   - { contact: { name, email, phone } }             (top-level contact)
	 *   - { answers: { contact: { name, email, phone } } } (contact nested inside answers)
	 *
	 * @param array $lead Lead payload.
	 * @return array Contact array (may be empty).
	 */
	public static function get_lead_contact( array $lead ): array {
		if ( isset( $lead['contact'] ) && is_array( $lead['contact'] ) && ! empty( $lead['contact'] ) ) {
			return $lead['contact'];
		}
		$answers = isset( $lead['answers'] ) && is_array( $lead['answers'] ) ? $lead['answers'] : [];
		if ( isset( $answers['contact'] ) && is_array( $answers['contact'] ) ) {
			return $answers['contact'];
		}
		return [];
	}

	/**
	 * Build intro HTML: email-style with name, charter type, boat type, country, dates; contact links. Falls back to intro_html when no lead.
	 *
	 * @param array  $lead Lead payload (answers, contact).
	 * @param string $intro_html Fallback intro HTML.
	 * @param string $contact_wa WhatsApp number.
	 * @param string $contact_email Email.
	 * @return string HTML.
	 */
	public static function build_intro_html( $lead, $intro_html, $contact_wa, $contact_email ) {
		// Always use the email-style intro; fill from lead when present, otherwise use generic placeholders.
		$answers = isset( $lead['answers'] ) && is_array( $lead['answers'] ) ? $lead['answers'] : [];
		$contact = self::get_lead_contact( $lead );

		// Handle both old { name } and new { firstName, lastName } contact formats.
		if ( ! empty( $contact['firstName'] ) ) {
			$first_name = trim( (string) $contact['firstName'] );
		} elseif ( ! empty( $contact['name'] ) ) {
			$_full = trim( (string) $contact['name'] );
			$first_name = trim( (string) ( strstr( $_full, ' ', true ) ?: $_full ) );
		} else {
			$first_name = '';
		}

		$charter_type = isset( $answers['charterType'] ) ? trim( (string) $answers['charterType'] ) : '';
		$boat_type    = isset( $answers['boatType'] ) ? trim( (string) $answers['boatType'] ) : '';
		$country      = isset( $answers['country'] ) ? trim( (string) $answers['country'] ) : '';
		$dates_str    = '';
		if ( ! empty( $answers['dates']['start'] ) ) {
			$dates_str = trim( (string) $answers['dates']['start'] );
		}
		$charter_label = $charter_type ? ucfirst( $charter_type ) : __( 'charter', 'sailscanner-proposals' );
		$boat_label    = $boat_type ? ucfirst( $boat_type ) : __( 'yacht', 'sailscanner-proposals' );
		$country_label = $country ?: __( 'your chosen area', 'sailscanner-proposals' );
		$dates_label   = $dates_str ? $dates_str : __( 'the specified dates', 'sailscanner-proposals' );

		$html = '';
		$html .= '<p>';
		if ( $first_name ) {
			$html .= sprintf( __( 'Hi %s,', 'sailscanner-proposals' ), esc_html( $first_name ) ) . '<br><br>';
		} else {
			$html .= __( 'Hi,', 'sailscanner-proposals' ) . '<br><br>';
		}
		$html .= sprintf(
			__( 'As requested, here is an example sailing itinerary and some yacht options for your %1$s %2$s charter in %3$s on %4$s.', 'sailscanner-proposals' ),
			esc_html( $charter_label ),
			esc_html( $boat_label ),
			esc_html( $country_label ),
			esc_html( $dates_label )
		) . '</p>';
		$html .= '<p>' . __( 'Please let me know your thoughts and if you need any more information.', 'sailscanner-proposals' ) . '</p>';
		$html .= '<p>' . __( 'You can contact me via email or WhatsApp using the links below.', 'sailscanner-proposals' ) . '</p>';
		$html .= '<p>' . __( 'Best regards,', 'sailscanner-proposals' ) . '<br>Chris</p>';
		if ( $contact_wa || $contact_email ) {
			$html .= '<p>';
			if ( $contact_wa ) {
				$wa_msg  = __( 'Hi, I have a question about my charter proposal.', 'sailscanner-proposals' );
				$wa_link = self::whatsapp_url( $contact_wa, $wa_msg );
				$html   .= '<a href="' . esc_url( $wa_link ) . '" class="ss-proposal-btn ss-proposal-btn-whatsapp" target="_blank" rel="noopener noreferrer">' . esc_html__( 'WhatsApp', 'sailscanner-proposals' ) . '</a> ';
			}
			if ( $contact_email ) {
				$html .= '<a href="mailto:' . esc_attr( $contact_email ) . '" class="ss-proposal-btn ss-proposal-btn-outline">' . esc_html__( 'Email', 'sailscanner-proposals' ) . '</a>';
			}
			$html .= '</p>';
		}
		return $html;
	}

	/**
	 * Render requirements section: lead.answers as styled grid with icons, or fallback to requirements list.
	 *
	 * @param array $lead Lead payload.
	 * @param array $requirements Fallback key-value list.
	 * @return string HTML (unescaped; use with echo in template).
	 */
	public static function render_requirements_html( $lead, $requirements ) {
		$answers = isset( $lead['answers'] ) && is_array( $lead['answers'] ) ? $lead['answers'] : [];
		if ( ! empty( $answers ) ) {
			$rows = [];
			$map = [
				'charterType'      => [ 'label' => __( 'Charter type', 'sailscanner-proposals' ), 'icon' => 'sailing' ],
				'boatType'          => [ 'label' => __( 'Boat type', 'sailscanner-proposals' ), 'icon' => 'directions_boat' ],
				'country'           => [ 'label' => __( 'Country', 'sailscanner-proposals' ), 'icon' => 'public' ],
				'region'            => [ 'label' => __( 'Region', 'sailscanner-proposals' ), 'icon' => 'map' ],
				'size'              => [ 'label' => __( 'Size', 'sailscanner-proposals' ), 'icon' => 'straighten' ],
				'cabins'            => [ 'label' => __( 'Cabins', 'sailscanner-proposals' ), 'icon' => 'bed' ],
				'budget'            => [ 'label' => __( 'Budget', 'sailscanner-proposals' ), 'icon' => 'payments' ],
				'experienceLevel'   => [ 'label' => __( 'Experience', 'sailscanner-proposals' ), 'icon' => 'school' ],
			];
		if ( ! empty( $answers['dates']['start'] ) ) {
			$dates_val = (string) $answers['dates']['start'];
			if ( ! empty( $answers['dates']['end'] ) ) {
				$dates_val .= ' → ' . (string) $answers['dates']['end'];
			}
			$rows[] = [ 'label' => __( 'Dates', 'sailscanner-proposals' ), 'icon' => 'calendar_today', 'value' => $dates_val ];
		}
			foreach ( $map as $key => $conf ) {
				if ( empty( $answers[ $key ] ) ) {
					continue;
				}
				$val = $answers[ $key ];
				if ( is_array( $val ) ) {
					$val = implode( ', ', array_map( 'strval', $val ) );
				}
				$rows[] = [ 'label' => $conf['label'], 'icon' => $conf['icon'], 'value' => (string) $val ];
			}
			if ( ! empty( $answers['crewServices'] ) && is_array( $answers['crewServices'] ) ) {
				$opts = array_filter( $answers['crewServices'] );
				if ( ! empty( $opts ) ) {
					$_svc_labels = [
						'chef'            => 'Chef',
						'cook'            => 'Chef / Cook',
						'provisioning'    => 'Provisioning',
						'airportTransfer' => 'Airport Transfer',
						'hostess'         => 'Hostess',
					];
					$_svc_names = array_map(
						fn( $k ) => $_svc_labels[ $k ] ?? ucfirst( (string) $k ),
						array_keys( $opts )
					);
					$rows[] = [
						'label' => __( 'Crew services', 'sailscanner-proposals' ),
						'icon'  => 'group',
						'value' => implode( ', ', $_svc_names ),
					];
				}
			}
			if ( empty( $rows ) ) {
				return '<p class="ss-proposal-muted">' . esc_html__( 'Summary of your charter request.', 'sailscanner-proposals' ) . '</p>';
			}
			$out = '<div class="ss-proposal-reqs-grid">';
			foreach ( $rows as $row ) {
				$out .= '<div class="ss-proposal-reqs-row">';
				$out .= '<span class="material-symbols-outlined ss-proposal-reqs-icon" aria-hidden="true">' . esc_html( $row['icon'] ) . '</span>';
				$out .= '<span class="ss-proposal-reqs-label">' . esc_html( $row['label'] ) . '</span>';
				$out .= '<span class="ss-proposal-reqs-value">' . esc_html( $row['value'] ) . '</span>';
				$out .= '</div>';
			}
			$out .= '</div>';
			return $out;
		}
		if ( ! empty( $requirements ) ) {
			$out = '<dl class="ss-proposal-reqs">';
			foreach ( $requirements as $key => $val ) {
				$out .= '<dt>' . esc_html( is_string( $key ) ? $key : '' ) . '</dt>';
				$out .= '<dd>' . esc_html( is_scalar( $val ) ? (string) $val : wp_json_encode( $val ) ) . '</dd>';
			}
			$out .= '</dl>';
			return $out;
		}
		return '<p class="ss-proposal-muted">' . esc_html__( 'Summary of your charter request.', 'sailscanner-proposals' ) . '</p>';
	}

	/**
	 * Decode any JSON \uXXXX Unicode escapes in a string (defence against double-encoding in stored meta).
	 * Safe to call on already-decoded strings — no-op if no \u sequences present.
	 *
	 * @param string $str Raw value from decoded JSON meta.
	 * @return string String with Unicode escapes replaced by their actual characters.
	 */
	private static function decode_unicode_escapes( $str ) {
		if ( ! is_string( $str ) || strpos( $str, '\u' ) === false ) {
			return $str;
		}
		return preg_replace_callback(
			'/\\\\u([0-9a-fA-F]{4})/',
			function ( $m ) {
				return mb_convert_encoding( pack( 'H*', $m[1] ), 'UTF-8', 'UCS-2BE' );
			},
			$str
		);
	}

	/**
	 * Render pricing as a full, structured table. Safe HTML via esc_html on all values.
	 * Shows: base price → discounts → charter price (total) → mandatory extras → optional extras.
	 *
	 * @param array       $prices    Same shape as get_yacht_display_data['prices'].
	 * @param bool        $compact   Unused; kept for backward compatibility.
	 * @param string      $opt_mode  'full' = all optional extras (default); 'requested' = only
	 *                               items the client requested (have a 'note' field), with a
	 *                               "View more extras" link appended.
	 * @param string      $detail_url URL of the yacht detail page (used in 'requested' mode).
	 * @return string HTML table or empty string if no prices.
	 */
	public static function render_pricing_table( $prices, $compact = false, $opt_mode = 'full', $detail_url = '' ) {
		if ( ! is_array( $prices ) || empty( $prices ) ) {
			return '';
		}

		$parse_extra = function ( $item ) {
			if ( is_array( $item ) ) {
				return [
					'label'  => self::decode_unicode_escapes( isset( $item['label'] ) ? (string) $item['label'] : '' ),
					'amount' => self::decode_unicode_escapes( isset( $item['amount'] ) ? (string) $item['amount'] : '' ),
				];
			}
			return [ 'label' => self::decode_unicode_escapes( (string) $item ), 'amount' => '' ];
		};

		$has_content = ! empty( $prices['base_price'] )
			|| ! empty( $prices['charter_price'] )
			|| ! empty( $prices['discounts'] )
			|| ! empty( $prices['mandatory_advance'] )
			|| ! empty( $prices['mandatory_base'] )
			|| ! empty( $prices['optional_extras'] );

		if ( ! $has_content ) {
			return '';
		}

		$section = function ( $label ) {
			return '<tr class="ss-proposal-pricing-section"><td colspan="2">' . esc_html( $label ) . '</td></tr>';
		};

		$out  = '<table class="ss-proposal-pricing-table">';
		$out .= '<thead><tr>';
		$out .= '<th scope="col">' . esc_html__( 'Item', 'sailscanner-proposals' ) . '</th>';
		$out .= '<th scope="col">' . esc_html__( 'Amount', 'sailscanner-proposals' ) . '</th>';
		$out .= '</tr></thead><tbody>';

		// Base price.
		if ( ! empty( $prices['base_price'] ) ) {
			$out .= '<tr><th scope="row">' . esc_html__( 'Base Price', 'sailscanner-proposals' ) . '</th>'
				. '<td>' . esc_html( self::decode_unicode_escapes( trim( (string) $prices['base_price'] ) ) ) . '</td></tr>';
		}

		// Discounts (individual rows).
		if ( ! empty( $prices['discounts'] ) && is_array( $prices['discounts'] ) ) {
			foreach ( $prices['discounts'] as $d ) {
				$row  = $parse_extra( $d );
				$out .= '<tr class="ss-proposal-pricing-discount"><th scope="row">' . esc_html( $row['label'] ) . '</th>'
					. '<td class="ss-proposal-pricing-negative">' . esc_html( $row['amount'] ) . '</td></tr>';
			}
		}

		// Charter price (the net total).
		if ( ! empty( $prices['charter_price'] ) ) {
			$out .= '<tr class="ss-proposal-pricing-total"><th scope="row">' . esc_html__( 'Charter Price', 'sailscanner-proposals' ) . '</th>'
				. '<td class="ss-proposal-pricing-charter">' . esc_html( self::decode_unicode_escapes( trim( (string) $prices['charter_price'] ) ) ) . '</td></tr>';
		}

		// Mandatory extras.
		$mandatory = array_merge(
			is_array( $prices['mandatory_advance'] ?? null ) ? $prices['mandatory_advance'] : [],
			is_array( $prices['mandatory_base'] ?? null )    ? $prices['mandatory_base']    : []
		);
		if ( ! empty( $mandatory ) ) {
			$out .= $section( __( 'Mandatory Extras', 'sailscanner-proposals' ) );
			foreach ( $mandatory as $m ) {
				$row  = $parse_extra( $m );
				$out .= '<tr><th scope="row">' . esc_html( $row['label'] ) . '</th>'
					. '<td>' . esc_html( $row['amount'] ) . '</td></tr>';
			}
		}

		// Optional extras — filter to requested-only when in 'requested' mode.
		$all_optionals     = ( ! empty( $prices['optional_extras'] ) && is_array( $prices['optional_extras'] ) )
			? $prices['optional_extras'] : [];
		$requested_only    = $opt_mode === 'requested';
		$extras_to_show    = $requested_only
			? array_values( array_filter( $all_optionals, fn( $e ) => ! empty( $e['note'] ) ) )
			: $all_optionals;
		$hidden_extra_count = $requested_only ? ( count( $all_optionals ) - count( $extras_to_show ) ) : 0;

		if ( ! empty( $extras_to_show ) ) {
			$out .= $section( __( 'Optional Extras', 'sailscanner-proposals' ) );
			foreach ( $extras_to_show as $extra ) {
				$row        = $parse_extra( $extra );
				$note_badge = '';
				if ( ! empty( $extra['note'] ) ) {
					$note_badge = ' <span class="ss-pricing-note-badge">(' . esc_html( (string) $extra['note'] ) . ')</span>';
				}
				$out .= '<tr><th scope="row">' . esc_html( $row['label'] ) . $note_badge . '</th>'
					. '<td>' . esc_html( $row['amount'] ) . '</td></tr>';
			}
		}

		$out .= '</tbody></table>';

		// In requested mode, append a "View more extras" link when there are hidden items.
		if ( $requested_only && $hidden_extra_count > 0 && $detail_url ) {
			$anchor_url = esc_url( rtrim( $detail_url, '/' ) . '/#pricing' );
			/* translators: %d: number of additional optional extras */
			$link_label = sprintf(
				_n( 'View %d more optional extra', 'View %d more optional extras', $hidden_extra_count, 'sailscanner-proposals' ),
				$hidden_extra_count
			);
			$out .= '<p class="ss-proposal-extras-more-link">'
				. '<a href="' . $anchor_url . '">'
				. esc_html( $link_label )
				. ' <span class="material-symbols-outlined" aria-hidden="true">arrow_forward</span>'
				. '</a>'
				. '</p>';
		} elseif ( $requested_only && empty( $extras_to_show ) && ! empty( $all_optionals ) && $detail_url ) {
			// No requested extras but extras exist — still show the link.
			$anchor_url = esc_url( rtrim( $detail_url, '/' ) . '/#pricing' );
			$out .= '<p class="ss-proposal-extras-more-link">'
				. '<a href="' . esc_url( $anchor_url ) . '">'
				. esc_html__( 'View optional extras', 'sailscanner-proposals' )
				. ' <span class="material-symbols-outlined" aria-hidden="true">arrow_forward</span>'
				. '</a>'
				. '</p>';
		}

		// If the price was pro-rated from a weekly rate, show a brief note below the table.
		if ( ! empty( $prices['prorated_note'] ) ) {
			$out .= '<p class="ss-proposal-pricing-prorated-note">'
				. '<span class="material-symbols-outlined" aria-hidden="true">info</span> '
				. esc_html( (string) $prices['prorated_note'] )
				. '</p>';
		}

		return $out;
	}

	/**
	 * Build WhatsApp link with prefilled message (no provider leakage).
	 *
	 * @param string $number E.164 or digits
	 * @param string $message Prefilled message
	 * @return string URL
	 */
	public static function whatsapp_url( $number, $message = '' ) {
		$number = preg_replace( '/[^0-9]/', '', $number );
		if ( ! $number ) {
			return '';
		}
		$url = 'https://wa.me/' . $number;
		if ( $message !== '' ) {
			$url .= '?text=' . rawurlencode( $message );
		}
		return esc_url( $url );
	}
}
