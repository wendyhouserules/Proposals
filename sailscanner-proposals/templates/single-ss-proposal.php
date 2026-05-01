<?php
/**
 * Proposal template: portal-style layout, sidebar on LEFT (fixed/sticky on desktop; at top on mobile).
 * Includes "How it works" section with process steps. No provider/operator names or MMK/NauSYS URLs.
 * Noindex set by SS_Proposal_SEO.
 *
 * @package SailScanner_Proposals
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

global $ss_proposal_post;
if ( ! $ss_proposal_post || $ss_proposal_post->post_type !== 'ss_proposal' ) {
	return;
}

$proposal_id = $ss_proposal_post->ID;
$yacht_ids   = get_post_meta( $proposal_id, 'ss_yacht_ids', true );
$yacht_ids   = is_array( $yacht_ids ) ? $yacht_ids : [];
$yacht_data  = get_post_meta( $proposal_id, 'ss_yacht_data', true );
if ( is_string( $yacht_data ) ) {
	$yacht_data = json_decode( $yacht_data, true );
}
$yacht_data  = is_array( $yacht_data ) ? $yacht_data : [];
$intro_html  = get_post_meta( $proposal_id, 'ss_intro_html', true );
$itinerary_html = get_post_meta( $proposal_id, 'ss_itinerary_html', true );
$notes_html  = get_post_meta( $proposal_id, 'ss_notes_html', true );
$contact_wa  = get_post_meta( $proposal_id, 'ss_contact_whatsapp', true );
$contact_email = get_post_meta( $proposal_id, 'ss_contact_email', true );
$requirements_json = get_post_meta( $proposal_id, 'ss_requirements_json', true );
$requirements = [];
if ( is_string( $requirements_json ) ) {
	$dec = json_decode( $requirements_json, true );
	if ( is_array( $dec ) ) {
		$requirements = $dec;
	}
}
$lead_json = get_post_meta( $proposal_id, 'ss_lead_json', true );
$lead = [];
if ( is_string( $lead_json ) ) {
	$dec = json_decode( $lead_json, true );
	if ( is_array( $dec ) ) {
		$lead = $dec;
	}
}
// Apply any admin-edited requirement overrides (ss_answers_override) without touching the original lead data.
$answers_override_json = get_post_meta( $proposal_id, 'ss_answers_override', true );
if ( is_string( $answers_override_json ) && $answers_override_json !== '' ) {
	$_override = json_decode( $answers_override_json, true );
	if ( is_array( $_override ) ) {
		if ( ! isset( $lead['answers'] ) || ! is_array( $lead['answers'] ) ) {
			$lead['answers'] = [];
		}
		foreach ( $_override as $_k => $_v ) {
			// 'dates' is a nested array; all other keys are flat strings.
			if ( $_k === 'dates' && is_array( $_v ) ) {
				$lead['answers']['dates'] = array_merge( $lead['answers']['dates'] ?? [], $_v );
			} elseif ( $_v !== '' && $_v !== null ) {
				$lead['answers'][ $_k ] = $_v;
			}
		}
	}
}
$itinerary_link_url      = get_post_meta( $proposal_id, 'ss_itinerary_link_url',      true );
$itinerary_link_title    = get_post_meta( $proposal_id, 'ss_itinerary_link_title',    true );
$itinerary_link_summary  = get_post_meta( $proposal_id, 'ss_itinerary_link_summary',  true );
$itinerary_link_image    = get_post_meta( $proposal_id, 'ss_itinerary_link_image',    true );
$itinerary_link_days     = get_post_meta( $proposal_id, 'ss_itinerary_link_days',     true );
$itinerary_link_distance = get_post_meta( $proposal_id, 'ss_itinerary_link_distance', true );
$itinerary_link_region   = get_post_meta( $proposal_id, 'ss_itinerary_link_region',   true );

// Yacht picks: use ss_yacht_ids, skipping trashed/deleted posts individually.
// Only fall back to ss_yacht_data when there are no IDs at all — never fall back just because
// some IDs were trashed, as that would resurrect deliberately removed yachts.
$yachts = [];
if ( ! empty( $yacht_ids ) ) {
	foreach ( $yacht_ids as $yid ) {
		$p = get_post( (int) $yid );
		// Skip posts that don't exist, wrong type, or have been trashed/deleted.
		if ( ! $p || $p->post_type !== 'ss_proposal_yacht' || $p->post_status !== 'publish' ) {
			continue;
		}
		$yachts[] = SS_Proposal_Helpers::get_yacht_display_data( (int) $yid );
	}
}
// Only fall back to raw ss_yacht_data if no published yacht posts exist at all.
if ( empty( $yachts ) && ! empty( $yacht_data ) ) {
	foreach ( $yacht_data as $i => $item ) {
		$yachts[] = SS_Proposal_Helpers::normalize_yacht_data_item( $item, $i );
	}
}
$yachts = array_filter( $yachts );

// Group-by-base: when enabled, bucket yachts by their charter base for sub-section display.
$group_by_base = (bool) get_post_meta( $proposal_id, 'ss_group_by_base', true );

/**
 * Build an ordered array of base groups: [ 'base_label' => [ yacht, ... ], ... ]
 * Base label comes from charter_json['base'] or falls back to 'Other'.
 */
$yacht_base_groups = []; // Populated only when $group_by_base is true.
if ( $group_by_base && ! empty( $yachts ) ) {
	foreach ( $yachts as $y ) {
		// 'charter' is the key returned by get_yacht_display_data() / normalize_yacht_data_item().
		$charter = is_array( $y['charter'] ?? null ) ? $y['charter'] : [];
		$base    = ! empty( $charter['base'] ) ? trim( $charter['base'] ) : __( 'Other', 'sailscanner-proposals' );
		// Shorten label: drop "Country, Region / " prefix for readability.
		// e.g. "Italy, Sicily / Furnari / Marina Portorosa" → "Furnari / Marina Portorosa"
		$base_parts = explode( ' / ', $base, 2 );
		$base_label = isset( $base_parts[1] ) ? $base_parts[1] : $base;
		if ( ! isset( $yacht_base_groups[ $base_label ] ) ) {
			$yacht_base_groups[ $base_label ] = [];
		}
		$yacht_base_groups[ $base_label ][] = $y;
	}
}

/**
 * Slugify a base label into a safe anchor ID.
 * e.g. "Furnari / Marina Portorosa" → "base-furnari-marina-portorosa"
 */
function ss_base_anchor( string $label ): string {
	$slug = strtolower( $label );
	$slug = preg_replace( '/[^a-z0-9]+/', '-', $slug );
	$slug = trim( $slug, '-' );
	return 'base-' . $slug;
}

// Intro: prefer editable post_content (block editor); fall back to auto-generated HTML.
// When using post_content, the template appends the CTA buttons so the editable text stays clean.
$_raw_content   = get_post_field( 'post_content', $proposal_id );
$intro_has_ctas = false;
if ( $_raw_content && trim( $_raw_content ) !== '' ) {
	$intro_to_show  = apply_filters( 'the_content', $_raw_content );
	$intro_has_ctas = false; // Buttons are appended by the template below.
} else {
	$intro_to_show  = SS_Proposal_Helpers::build_intro_html( $lead, $intro_html, $contact_wa, $contact_email );
	$intro_has_ctas = true; // build_intro_html already includes CTA buttons.
}

wp_enqueue_style( 'ss-proposals-portal', SAILSCANNER_PROPOSALS_URL . 'assets/proposal-portal.css', [], SAILSCANNER_PROPOSALS_VERSION );
wp_enqueue_style(
	'ss-proposals-material-symbols',
	'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0',
	[],
	null
);

get_header();
?>

<div class="ss-proposal-portal" id="ss-proposal">

	<?php
	$_lead_contact = SS_Proposal_Helpers::get_lead_contact( $lead );
	if ( ! empty( $_lead_contact['firstName'] ) ) {
		$client_name = sanitize_text_field( (string) $_lead_contact['firstName'] );
	} elseif ( ! empty( $_lead_contact['name'] ) ) {
		$_full_name  = trim( (string) $_lead_contact['name'] );
		$client_name = sanitize_text_field( (string) ( strstr( $_full_name, ' ', true ) ?: $_full_name ) );
	} else {
		$client_name = '';
	}
	$proposal_date = get_the_date( 'j F Y', $proposal_id );
	?>
	<div class="ss-proposal-header">
		<div class="ss-proposal-header-inner">
			<div class="ss-proposal-header-title-row">
				<span class="material-symbols-outlined ss-proposal-header-doc-icon" aria-hidden="true">description</span>
				<div class="ss-proposal-header-title-text">
					<h1 class="ss-proposal-header-title"><?php esc_html_e( 'Your Sailing Charter Proposal', 'sailscanner-proposals' ); ?></h1>
					<p class="ss-proposal-header-subtitle"><?php esc_html_e( 'Tailored yacht charter options, prepared exclusively for you.', 'sailscanner-proposals' ); ?></p>
				</div>
			</div>
			<hr class="ss-proposal-header-divider" />
			<div class="ss-proposal-header-meta">
				<div class="ss-proposal-header-meta-item">
					<span class="material-symbols-outlined ss-proposal-header-meta-icon" aria-hidden="true">calendar_month</span>
					<div class="ss-proposal-header-meta-body">
						<span class="ss-proposal-header-meta-label"><?php esc_html_e( 'Date Created', 'sailscanner-proposals' ); ?></span>
						<span class="ss-proposal-header-meta-value"><?php echo esc_html( $proposal_date ); ?></span>
					</div>
				</div>
				<?php if ( $client_name ) : ?>
				<div class="ss-proposal-header-meta-item">
					<span class="material-symbols-outlined ss-proposal-header-meta-icon" aria-hidden="true">person</span>
					<div class="ss-proposal-header-meta-body">
						<span class="ss-proposal-header-meta-label"><?php esc_html_e( 'Prepared For', 'sailscanner-proposals' ); ?></span>
						<span class="ss-proposal-header-meta-value"><?php echo esc_html( $client_name ); ?></span>
					</div>
				</div>
				<?php endif; ?>
				<div class="ss-proposal-header-meta-item">
					<span class="material-symbols-outlined ss-proposal-header-meta-icon" aria-hidden="true">manage_accounts</span>
					<div class="ss-proposal-header-meta-body">
						<span class="ss-proposal-header-meta-label"><?php esc_html_e( 'Prepared By', 'sailscanner-proposals' ); ?></span>
						<span class="ss-proposal-header-meta-value">
							<?php esc_html_e( 'Christopher Hennessy', 'sailscanner-proposals' ); ?>
							<span class="ss-proposal-header-meta-email">(chris@sailscanner.ai)</span>
						</span>
					</div>
				</div>
			</div>
		</div>
	</div>

	<div class="ss-proposal-layout">
		<aside class="ss-proposal-sidebar ss-proposal-sidebar-nav-only" id="ss-proposal-sidebar" aria-label="<?php esc_attr_e( 'Proposal navigation', 'sailscanner-proposals' ); ?>">
			<div class="ss-proposal-sidebar-inner">
				<h2 class="ss-proposal-contents-title"><?php esc_html_e( 'Contents', 'sailscanner-proposals' ); ?></h2>
				<nav class="ss-proposal-nav ss-proposal-nav-cards" aria-label="<?php esc_attr_e( 'Page sections', 'sailscanner-proposals' ); ?>">
					<ul>
						<?php if ( $intro_to_show ) : ?>
						<li><a href="#intro" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">description</span><?php esc_html_e( 'Introduction', 'sailscanner-proposals' ); ?></a></li>
						<?php endif; ?>
						<li><a href="#requirements" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">checklist</span><?php esc_html_e( 'Your Requirements', 'sailscanner-proposals' ); ?></a></li>
						<?php if ( $itinerary_html || ( $itinerary_link_url && ( $itinerary_link_title || $itinerary_link_summary ) ) ) : ?>
						<li><a href="#itinerary" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">map</span><?php esc_html_e( 'Example Itinerary', 'sailscanner-proposals' ); ?></a></li>
						<?php endif; ?>
						<?php if ( ! empty( $yachts ) ) : ?>
						<li>
							<a href="#yacht-selection" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">sailing</span><?php esc_html_e( 'Yacht Selection', 'sailscanner-proposals' ); ?></a>
							<?php if ( $group_by_base && ! empty( $yacht_base_groups ) ) : ?>
							<ul class="ss-proposal-nav-subnav">
								<?php foreach ( $yacht_base_groups as $_base_label => $_base_yachts ) : ?>
								<li><a href="#<?php echo esc_attr( ss_base_anchor( $_base_label ) ); ?>" class="ss-proposal-nav-sublink"><?php echo esc_html( $_base_label ); ?> <span class="ss-proposal-nav-subcount">(<?php echo count( $_base_yachts ); ?>)</span></a></li>
								<?php endforeach; ?>
							</ul>
							<?php endif; ?>
						</li>
						<?php endif; ?>
						<li><a href="#how-it-works" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">settings</span><?php esc_html_e( 'How it Works', 'sailscanner-proposals' ); ?></a></li>
						<li><a href="#charter-insurance" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">shield</span><?php esc_html_e( 'Charter Insurance', 'sailscanner-proposals' ); ?></a></li>
						<li><a href="#next-steps" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">check_circle</span><?php esc_html_e( 'Next Steps', 'sailscanner-proposals' ); ?></a></li>
						<li><a href="#contact" class="ss-proposal-nav-link"><span class="material-symbols-outlined ss-proposal-nav-icon" aria-hidden="true">mail</span><?php esc_html_e( 'Contact', 'sailscanner-proposals' ); ?></a></li>
					</ul>
				</nav>
			</div>
		</aside>

		<main class="ss-proposal-main" id="ss-proposal-main">
			<section class="ss-proposal-section ss-proposal-intro-requirements" id="intro">
				<div class="ss-proposal-content ss-proposal-card ss-proposal-requirements-block">
				<?php if ( $intro_to_show ) : ?>
					<h2 class="ss-proposal-h2"><?php esc_html_e( 'Welcome to SailScanner', 'sailscanner-proposals' ); ?></h2>
					<?php echo wp_kses_post( $intro_to_show ); ?>
					<?php if ( ! $intro_has_ctas && ( $contact_wa || $contact_email ) ) : ?>
					<p class="ss-proposal-intro-ctas">
						<?php if ( $contact_wa ) :
							$_wa_link = SS_Proposal_Helpers::whatsapp_url( $contact_wa, __( 'Hi, I have a question about my charter proposal.', 'sailscanner-proposals' ) );
						?>
						<a href="<?php echo esc_url( $_wa_link ); ?>" class="ss-proposal-btn ss-proposal-btn-whatsapp" target="_blank" rel="noopener noreferrer"><?php esc_html_e( 'WhatsApp', 'sailscanner-proposals' ); ?></a>
						<?php endif; ?>
						<?php if ( $contact_email ) : ?>
						<a href="mailto:<?php echo esc_attr( $contact_email ); ?>" class="ss-proposal-btn ss-proposal-btn-outline"><?php esc_html_e( 'Email', 'sailscanner-proposals' ); ?></a>
						<?php endif; ?>
					</p>
					<?php endif; ?>
					<hr class="ss-proposal-card-hr" />
				<?php endif; ?>
					<h2 class="ss-proposal-h2" id="requirements"><?php esc_html_e( 'Your Requirements', 'sailscanner-proposals' ); ?></h2>
					<?php echo SS_Proposal_Helpers::render_requirements_html( $lead, $requirements ); ?>
				</div>
			</section>
			<hr class="ss-proposal-section-hr" />

		<?php if ( $itinerary_html || ( $itinerary_link_url && ( $itinerary_link_title || $itinerary_link_summary ) ) ) : ?>
			<section class="ss-proposal-section" id="itinerary">
				<h2 class="ss-proposal-h2"><?php esc_html_e( 'Example Itinerary', 'sailscanner-proposals' ); ?></h2>

				<?php if ( $itinerary_link_url && ( $itinerary_link_title || $itinerary_link_summary ) ) :
					// Build the "N-Day Sailing Itinerary · Region" tag line.
					$_itin_tag_parts = [];
					if ( $itinerary_link_days ) {
						$_itin_tag_parts[] = esc_html( $itinerary_link_days ) . '-Day Sailing Itinerary';
					}
					if ( $itinerary_link_region ) {
						$_itin_tag_parts[] = esc_html( $itinerary_link_region );
					}
					$_itin_tag = implode( ' · ', $_itin_tag_parts );
				?>
				<div class="ss-proposal-itinerary-card ss-proposal-card">
					<?php if ( $itinerary_link_image ) : ?>
					<a href="<?php echo esc_url( $itinerary_link_url ); ?>" class="ss-proposal-itinerary-card-img-wrap" target="_blank" rel="noopener noreferrer">
						<img src="<?php echo esc_url( $itinerary_link_image ); ?>"
							alt="<?php echo esc_attr( $itinerary_link_title ); ?>"
							class="ss-proposal-itinerary-card-img" />
					</a>
					<?php endif; ?>

					<div class="ss-proposal-itinerary-card-body">
						<?php if ( $_itin_tag ) : ?>
						<div class="ss-proposal-itinerary-card-tag"><?php echo $_itin_tag; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?></div>
						<?php endif; ?>

						<?php if ( $itinerary_link_title ) : ?>
						<h3 class="ss-proposal-itinerary-card-title"><?php echo esc_html( $itinerary_link_title ); ?></h3>
						<?php endif; ?>

						<?php if ( $itinerary_link_days || $itinerary_link_distance ) : ?>
						<div class="ss-proposal-itinerary-card-meta">
							<?php if ( $itinerary_link_days ) : ?>
							<span class="ss-itin-meta-pill">
								<span class="material-symbols-outlined" aria-hidden="true">calendar_month</span>
								<?php echo esc_html( $itinerary_link_days ); ?> days
							</span>
							<?php endif; ?>
							<?php if ( $itinerary_link_distance ) : ?>
							<span class="ss-itin-meta-pill">
								<span class="material-symbols-outlined" aria-hidden="true">conversion_path</span>
								<?php echo esc_html( $itinerary_link_distance ); ?>
							</span>
							<?php endif; ?>
						</div>
						<?php endif; ?>

						<?php if ( $itinerary_link_summary ) : ?>
						<p class="ss-proposal-itinerary-card-summary"><?php echo esc_html( $itinerary_link_summary ); ?></p>
						<?php endif; ?>

						<a href="<?php echo esc_url( $itinerary_link_url ); ?>"
							class="ss-proposal-btn ss-proposal-btn-primary ss-proposal-itinerary-card-cta"
							target="_blank" rel="noopener noreferrer">
							<span class="material-symbols-outlined" aria-hidden="true">map</span>
							<?php esc_html_e( 'View Day-by-Day Itinerary', 'sailscanner-proposals' ); ?>
						</a>
					</div>
				</div>
				<?php endif; ?>

				<?php if ( $itinerary_html ) : ?>
				<div class="ss-proposal-content ss-proposal-card"><?php echo wp_kses_post( $itinerary_html ); ?></div>
				<?php endif; ?>
			</section>
			<hr class="ss-proposal-section-hr" />
		<?php endif; ?>

			<?php if ( ! empty( $yachts ) ) : ?>
				<section class="ss-proposal-section ss-proposal-yachts" id="yacht-selection">
					<h2 class="ss-proposal-h2"><?php esc_html_e( 'Yacht Selection', 'sailscanner-proposals' ); ?></h2>

					<?php
					/**
					 * Build a flat render list so card markup only appears once.
					 * Each item is either a yacht array (render a card) or a marker:
					 *   ['__m' => 'base_open',  'label' => string, 'count' => int]
					 *   ['__m' => 'base_close']
					 *   ['__m' => 'cards_open']
					 *   ['__m' => 'cards_close']
					 */
					$_render_list = [];
					if ( $group_by_base && ! empty( $yacht_base_groups ) ) {
						foreach ( $yacht_base_groups as $_bl => $_by ) {
							$_render_list[] = [ '__m' => 'base_open',  'label' => $_bl, 'count' => count( $_by ) ];
							foreach ( $_by as $_y ) {
								$_render_list[] = $_y;
							}
							$_render_list[] = [ '__m' => 'base_close' ];
						}
					} else {
						$_render_list[] = [ '__m' => 'cards_open' ];
						foreach ( $yachts as $_y ) {
							$_render_list[] = $_y;
						}
						$_render_list[] = [ '__m' => 'cards_close' ];
					}
					foreach ( $_render_list as $_item ) :
						$_m = $_item['__m'] ?? null;
						if ( $_m === 'base_open' ) :
					?>
						<div class="ss-proposal-base-group" id="<?php echo esc_attr( ss_base_anchor( $_item['label'] ) ); ?>">
							<h3 class="ss-proposal-base-group-heading">
								<span class="material-symbols-outlined" aria-hidden="true">anchor</span>
								<?php echo esc_html( $_item['label'] ); ?>
								<span class="ss-proposal-base-group-count">(<?php echo (int) $_item['count']; ?> <?php esc_html_e( 'options', 'sailscanner-proposals' ); ?>)</span>
							</h3>
							<div class="ss-proposal-yacht-cards">
					<?php elseif ( $_m === 'base_close' ) : ?>
							</div><!-- /.ss-proposal-yacht-cards -->
						</div><!-- /.ss-proposal-base-group -->
					<?php elseif ( $_m === 'cards_open' ) : ?>
					<div class="ss-proposal-yacht-cards">
					<?php elseif ( $_m === 'cards_close' ) : ?>
					</div><!-- /.ss-proposal-yacht-cards -->
					<?php else : $yacht = $_item; ?>
					<?php /* ↓ yacht card — $yacht is set above */ ?>
							<?php
							$wa_message = sprintf(
								/* translators: yacht name */
								__( 'Hi, I\'d like to know more about %s from my proposal.', 'sailscanner-proposals' ),
								$yacht['display_name']
							);
							$wa_url = $contact_wa ? SS_Proposal_Helpers::whatsapp_url( $contact_wa, $wa_message ) : '';

							// Build filtered image list: skip generic MMK placeholder images (no real name param).
							$gallery_images = array_values( array_filter( (array) $yacht['images'], function( $url ) {
								return SS_Proposal_Helpers::is_real_yacht_image( $url );
							} ) );
							// Fallback: use image_url if gallery is empty and it passes the same check.
							if ( empty( $gallery_images ) && SS_Proposal_Helpers::is_real_yacht_image( $yacht['image_url'] ?? '' ) ) {
								$gallery_images = [ $yacht['image_url'] ];
							}
						$gallery_id  = 'ssg-' . absint( $yacht['id'] );
						$is_crewed   = ! empty( $yacht['charter']['crewed'] );
						?>
						<article class="ss-proposal-yacht-card" id="yacht-<?php echo absint( $yacht['id'] ); ?>">

							<!-- Gallery: main image + scrollable thumbnails -->
							<div class="ss-proposal-yacht-gallery" id="<?php echo esc_attr( $gallery_id ); ?>">
								<div class="ss-proposal-yacht-gallery-main">
									<?php if ( $is_crewed ) : ?>
										<span class="ss-proposal-crewed-badge" aria-label="<?php esc_attr_e( 'Crewed charter', 'sailscanner-proposals' ); ?>"><?php esc_html_e( 'Crewed', 'sailscanner-proposals' ); ?></span>
									<?php endif; ?>
									<?php if ( ! empty( $gallery_images ) ) : ?>
										<img class="ss-proposal-gallery-main-img"
											src="<?php echo esc_url( $gallery_images[0] ); ?>"
											alt="<?php echo esc_attr( $yacht['display_name'] ); ?>"
											loading="lazy" />
									<?php else : ?>
										<div class="ss-proposal-yacht-gallery-placeholder">
											<span class="material-symbols-outlined" aria-hidden="true">sailing</span>
										</div>
									<?php endif; ?>
								</div>
									<?php if ( count( $gallery_images ) > 1 ) : ?>
										<div class="ss-proposal-yacht-gallery-thumbs" role="list" aria-label="<?php esc_attr_e( 'Yacht photos', 'sailscanner-proposals' ); ?>">
											<?php foreach ( $gallery_images as $ti => $thumb_url ) : ?>
												<button class="ss-proposal-yacht-gallery-thumb<?php echo $ti === 0 ? ' is-active' : ''; ?>"
													type="button"
													data-gallery="<?php echo esc_attr( $gallery_id ); ?>"
													data-src="<?php echo esc_url( $thumb_url ); ?>"
													aria-label="<?php echo esc_attr( sprintf( __( 'View photo %d', 'sailscanner-proposals' ), $ti + 1 ) ); ?>"
													role="listitem">
													<img src="<?php echo esc_url( $thumb_url ); ?>" alt="" loading="lazy" />
												</button>
											<?php endforeach; ?>
										</div>
									<?php endif; ?>
								</div>

								<!-- Card body: title, specs, charter details, pricing + equipment (two-col), CTAs -->
								<div class="ss-proposal-yacht-card-body">
									<h3 class="ss-proposal-yacht-card-title">
										<a href="<?php echo esc_url( $yacht['url'] ); ?>"><?php echo esc_html( $yacht['display_name'] ); ?></a>
									</h3>

									<?php if ( ! empty( $yacht['specs'] ) ) : ?>
										<div class="ss-proposal-yacht-specs-box">
											<?php foreach ( array_slice( $yacht['specs'], 0, 6 ) as $spec ) : ?>
												<div class="ss-proposal-yacht-spec-item">
													<span class="ss-proposal-yacht-spec-label"><?php echo esc_html( $spec['label'] ); ?></span>
													<span class="ss-proposal-yacht-spec-value"><?php echo esc_html( $spec['value'] ); ?></span>
												</div>
											<?php endforeach; ?>
										</div>
									<?php else : ?>
										<ul class="ss-proposal-yacht-facts">
											<?php if ( ! empty( $yacht['cabins'] ) ) : ?><li><?php echo absint( $yacht['cabins'] ); ?> <?php esc_html_e( 'cabins', 'sailscanner-proposals' ); ?></li><?php endif; ?>
											<?php if ( ! empty( $yacht['berths'] ) ) : ?><li><?php echo absint( $yacht['berths'] ); ?> <?php esc_html_e( 'berths', 'sailscanner-proposals' ); ?></li><?php endif; ?>
											<?php if ( ! empty( $yacht['length_m'] ) ) : ?><li><?php echo esc_html( $yacht['length_m'] ); ?>m</li><?php endif; ?>
											<?php if ( ! empty( $yacht['year'] ) ) : ?><li><?php echo absint( $yacht['year'] ); ?></li><?php endif; ?>
											<?php if ( ! empty( $yacht['base_name'] ) ) : ?><li><?php echo esc_html( $yacht['base_name'] ); ?></li><?php endif; ?>
										</ul>
									<?php endif; ?>

								<?php
								$charter     = is_array( $yacht['charter'] ?? null ) ? $yacht['charter'] : [];
								$charter_html = SS_Proposal_Helpers::render_charter_slots( $charter );
								$has_charter  = $charter_html !== '';
								$has_prices   = ! empty( $yacht['prices'] ) && is_array( $yacht['prices'] );
								$has_equip    = ! empty( $yacht['highlights'] );
								?>

								<?php if ( $has_charter ) : ?>
									<?php echo $charter_html; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>
								<?php endif; ?>

									<!-- Pricing + Equipment in two columns on large screens -->
									<div class="ss-proposal-yacht-body-grid">
										<?php if ( $has_prices || $has_charter ) : ?>
											<div class="ss-proposal-yacht-body-col-main">
												<?php
												if ( $has_prices ) {
													$pricing_html = SS_Proposal_Helpers::render_pricing_table(
														$yacht['prices'],
														false,
														'requested',
														$yacht['url'] ?? ''
													);
													if ( $pricing_html !== '' ) {
														echo '<h4 class="ss-proposal-yacht-section-heading">' . esc_html__( 'Pricing', 'sailscanner-proposals' ) . '</h4>';
														echo $pricing_html; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped
													}
												}
												?>
											</div>
										<?php endif; ?>
										<?php if ( $has_equip ) : ?>
											<div class="ss-proposal-yacht-body-col-side">
												<h4 class="ss-proposal-yacht-section-heading"><?php esc_html_e( 'Equipment & Features', 'sailscanner-proposals' ); ?></h4>
										<div class="ss-proposal-yacht-equipment">
												<?php if ( $is_crewed ) : ?>
													<span class="ss-proposal-yacht-pill ss-proposal-yacht-pill--crewed"><?php esc_html_e( 'Crewed', 'sailscanner-proposals' ); ?></span>
												<?php endif; ?>
												<?php foreach ( $yacht['highlights'] as $h ) : ?>
													<span class="ss-proposal-yacht-pill"><?php echo esc_html( $h ); ?></span>
												<?php endforeach; ?>
												</div>
											</div>
										<?php endif; ?>
									</div>

									<div class="ss-proposal-yacht-ctas">
										<a href="<?php echo esc_url( $yacht['url'] ); ?>" class="ss-proposal-btn ss-proposal-btn-primary"><?php esc_html_e( 'View details', 'sailscanner-proposals' ); ?></a>
										<?php if ( $wa_url ) : ?>
											<a href="<?php echo esc_url( $wa_url ); ?>" class="ss-proposal-btn ss-proposal-btn-whatsapp" target="_blank" rel="noopener noreferrer"><?php esc_html_e( 'Shortlist / Ask', 'sailscanner-proposals' ); ?></a>
										<?php endif; ?>
									</div>
								</div>
							</article>
					<?php endif; // end render-list item dispatch ?>
					<?php endforeach; // end render list loop ?>

					<script>
					(function () {
						function ssGallerySwap(btn) {
							var gid     = btn.getAttribute('data-gallery');
							var src     = btn.getAttribute('data-src');
							var gallery = document.getElementById(gid);
							if (!gallery) return;
							var main = gallery.querySelector('.ss-proposal-gallery-main-img');
							if (main) main.src = src;
							gallery.querySelectorAll('.ss-proposal-yacht-gallery-thumb').forEach(function (t) {
								t.classList.remove('is-active');
							});
							btn.classList.add('is-active');
						}
						document.addEventListener('click', function (e) {
							var btn = e.target.closest('.ss-proposal-yacht-gallery-thumb');
							if (btn) ssGallerySwap(btn);
						});
					})();
					</script>
				</section>
				<hr class="ss-proposal-section-hr" />
			<?php endif; ?>

		<section class="ss-proposal-section" id="how-it-works">
			<h2 class="ss-proposal-h2"><?php esc_html_e( 'How it Works', 'sailscanner-proposals' ); ?></h2>
			<div class="ss-proposal-how-timeline">
				<div class="ss-proposal-how-step">
					<div class="ss-proposal-how-num" aria-hidden="true">1</div>
					<div class="ss-proposal-how-step-text">
						<div class="ss-proposal-how-badge">
							<span class="material-symbols-outlined" aria-hidden="true">bolt</span>
							<?php esc_html_e( 'Live pricing & availability', 'sailscanner-proposals' ); ?>
						</div>
						<h3 class="ss-proposal-how-step-title"><?php esc_html_e( 'Review your yacht options', 'sailscanner-proposals' ); ?></h3>
						<p class="ss-proposal-how-step-summary"><?php esc_html_e( "Browse the yachts we've selected for you. Each one shows live pricing and real availability for your dates. Take your time comparing specs, layout, and price. If anything is unclear or you'd like more detail on a yacht, just get in touch.", 'sailscanner-proposals' ); ?></p>
					</div>
				</div>
				<div class="ss-proposal-how-step">
					<div class="ss-proposal-how-num" aria-hidden="true">2</div>
					<div class="ss-proposal-how-step-text">
						<h3 class="ss-proposal-how-step-title"><?php esc_html_e( 'Want different or more options?', 'sailscanner-proposals' ); ?></h3>
						<p class="ss-proposal-how-step-summary"><?php esc_html_e( "Not quite what you were looking for? We're happy to revise this proposal with different yachts, alternative bases, or a wider range of options. Just let us know what you'd like to see and we'll update it for you.", 'sailscanner-proposals' ); ?></p>
					</div>
				</div>
				<div class="ss-proposal-how-step">
					<div class="ss-proposal-how-num" aria-hidden="true">3</div>
					<div class="ss-proposal-how-step-text">
						<h3 class="ss-proposal-how-step-title"><?php esc_html_e( 'Place an option to reserve a yacht', 'sailscanner-proposals' ); ?></h3>
						<p class="ss-proposal-how-step-summary"><?php esc_html_e( "Found a yacht you like but not quite ready to commit? We can place an option on it, holding your dates while you make your decision. No cost and no obligation.", 'sailscanner-proposals' ); ?></p>
						<span class="ss-proposal-how-tag"><?php esc_html_e( 'No cost · No obligation', 'sailscanner-proposals' ); ?></span>
					</div>
				</div>
				<div class="ss-proposal-how-step">
					<div class="ss-proposal-how-num" aria-hidden="true">4</div>
					<div class="ss-proposal-how-step-text">
						<h3 class="ss-proposal-how-step-title"><?php esc_html_e( 'Confirm with an initial deposit', 'sailscanner-proposals' ); ?></h3>
						<p class="ss-proposal-how-step-summary"><?php esc_html_e( "Once you're happy to go ahead, an initial deposit payment secures your booking. We handle all the paperwork and confirm everything directly with the charter company on your behalf.", 'sailscanner-proposals' ); ?></p>
						<span class="ss-proposal-how-tag"><?php esc_html_e( 'Booking confirmed', 'sailscanner-proposals' ); ?></span>
					</div>
				</div>
				<div class="ss-proposal-how-step">
					<div class="ss-proposal-how-num ss-proposal-how-num--icon" aria-label="<?php esc_attr_e( 'Ongoing support', 'sailscanner-proposals' ); ?>">
						<span class="material-symbols-outlined" aria-hidden="true">support_agent</span>
					</div>
					<div class="ss-proposal-how-step-text">
						<h3 class="ss-proposal-how-step-title"><?php esc_html_e( "We're with you throughout", 'sailscanner-proposals' ); ?></h3>
						<p class="ss-proposal-how-step-summary"><?php esc_html_e( "From booking to the moment you step on board, we're available to answer questions, advise on provisioning, and help with anything you need. Sail away with complete peace of mind.", 'sailscanner-proposals' ); ?></p>
					</div>
				</div>
			</div>
		</section>
			<hr class="ss-proposal-section-hr" />

			<section class="ss-proposal-section" id="charter-insurance">
				<h2 class="ss-proposal-h2"><?php esc_html_e( 'Charter Insurance', 'sailscanner-proposals' ); ?></h2>
				<div class="ss-proposal-content ss-proposal-card ss-proposal-insurance-card">
					<p class="ss-proposal-insurance-intro"><?php esc_html_e( "A charter holiday is a significant investment, and the unexpected can ruin it. Topsail specialise in charter travel insurance, giving you and your crew complete peace of mind from the moment you book to the moment you return.", 'sailscanner-proposals' ); ?></p>
					<div class="ss-proposal-insurance-grid">
						<div class="ss-proposal-insurance-item">
							<span class="ss-proposal-insurance-dot" aria-hidden="true"></span>
							<div>
								<p class="ss-proposal-insurance-item-title"><?php esc_html_e( 'Trip cancellation & curtailment', 'sailscanner-proposals' ); ?></p>
								<p class="ss-proposal-insurance-item-body"><?php esc_html_e( 'Protect your deposit and full charter costs if plans change before or during your trip.', 'sailscanner-proposals' ); ?></p>
							</div>
						</div>
						<div class="ss-proposal-insurance-item">
							<span class="ss-proposal-insurance-dot" aria-hidden="true"></span>
							<div>
								<p class="ss-proposal-insurance-item-title"><?php esc_html_e( 'Emergency medical & repatriation', 'sailscanner-proposals' ); ?></p>
								<p class="ss-proposal-insurance-item-body"><?php esc_html_e( 'Comprehensive cover for accidents and illness at sea, including repatriation home.', 'sailscanner-proposals' ); ?></p>
							</div>
						</div>
						<div class="ss-proposal-insurance-item">
							<span class="ss-proposal-insurance-dot" aria-hidden="true"></span>
							<div>
								<p class="ss-proposal-insurance-item-title"><?php esc_html_e( 'Baggage & personal property', 'sailscanner-proposals' ); ?></p>
								<p class="ss-proposal-insurance-item-body"><?php esc_html_e( 'Cover for lost, stolen or damaged luggage, electronics and valuables.', 'sailscanner-proposals' ); ?></p>
							</div>
						</div>
						<div class="ss-proposal-insurance-item">
							<span class="ss-proposal-insurance-dot" aria-hidden="true"></span>
							<div>
								<p class="ss-proposal-insurance-item-title"><?php esc_html_e( 'Legal expenses & liability', 'sailscanner-proposals' ); ?></p>
								<p class="ss-proposal-insurance-item-body"><?php esc_html_e( 'Protection against third-party claims and unexpected legal costs during your charter.', 'sailscanner-proposals' ); ?></p>
							</div>
						</div>
					</div>
					<a href="https://www.topsailinsurance.com/travel-insurance/charter-travel-insurance" class="ss-proposal-btn ss-proposal-btn-primary" target="_blank" rel="noopener noreferrer"><?php esc_html_e( 'Get a free quote from Topsail', 'sailscanner-proposals' ); ?></a>
					<p class="ss-proposal-insurance-note ss-proposal-muted"><?php esc_html_e( 'Topsail Insurance is a SailScanner verified partner. Charter insurance is strongly recommended for all bookings.', 'sailscanner-proposals' ); ?></p>
				</div>
			</section>
			<hr class="ss-proposal-section-hr" />

			<section class="ss-proposal-section" id="next-steps">
				<h2 class="ss-proposal-h2"><?php esc_html_e( 'Next Steps', 'sailscanner-proposals' ); ?></h2>
				<div class="ss-proposal-next-cards">
					<div class="ss-proposal-next-card">
						<div class="ss-proposal-next-num" aria-hidden="true">1</div>
						<h3 class="ss-proposal-next-card-title"><?php esc_html_e( 'Browse your shortlist', 'sailscanner-proposals' ); ?></h3>
						<p class="ss-proposal-next-card-body"><?php esc_html_e( "Review the yachts we've selected, compare specs and pricing, and note your favourites.", 'sailscanner-proposals' ); ?></p>
					</div>
					<div class="ss-proposal-next-card">
						<div class="ss-proposal-next-num" aria-hidden="true">2</div>
						<h3 class="ss-proposal-next-card-title"><?php esc_html_e( 'Ask us anything', 'sailscanner-proposals' ); ?></h3>
						<p class="ss-proposal-next-card-body"><?php esc_html_e( 'Got questions? Message us on WhatsApp. We reply fast, usually within the hour.', 'sailscanner-proposals' ); ?></p>
					</div>
					<div class="ss-proposal-next-card">
						<div class="ss-proposal-next-num" aria-hidden="true">3</div>
						<h3 class="ss-proposal-next-card-title"><?php esc_html_e( 'Reserve your yacht', 'sailscanner-proposals' ); ?></h3>
						<p class="ss-proposal-next-card-body"><?php esc_html_e( "Ready to proceed? We'll hold your preferred yacht while you finalise your decision.", 'sailscanner-proposals' ); ?></p>
					</div>
				</div>
				<div class="ss-proposal-next-cta">
					<?php if ( $contact_wa ) : ?>
						<?php
						$wa_ns_link = SS_Proposal_Helpers::whatsapp_url( $contact_wa, __( 'Hi, I have a question about my charter proposal.', 'sailscanner-proposals' ) );
						?>
						<a href="<?php echo esc_url( $wa_ns_link ); ?>" class="ss-proposal-btn ss-proposal-btn-whatsapp" target="_blank" rel="noopener noreferrer"><?php esc_html_e( 'Chat on WhatsApp', 'sailscanner-proposals' ); ?></a>
					<?php endif; ?>
					<?php if ( $contact_email ) : ?>
						<a href="mailto:<?php echo esc_attr( $contact_email ); ?>" class="ss-proposal-btn ss-proposal-btn-outline"><?php esc_html_e( 'Email us', 'sailscanner-proposals' ); ?></a>
					<?php endif; ?>
				</div>
				<p class="ss-proposal-muted"><?php esc_html_e( 'Prices shown are live rates for your exact dates. Contact us to hold a yacht and lock in your booking.', 'sailscanner-proposals' ); ?></p>
			</section>
			<hr class="ss-proposal-section-hr" />

			<section class="ss-proposal-section" id="contact">
				<h2 class="ss-proposal-h2"><?php esc_html_e( 'Contact', 'sailscanner-proposals' ); ?></h2>
				<div class="ss-proposal-content ss-proposal-card">
					<div class="ss-proposal-contact-inner">
						<div class="ss-proposal-contact-avatar" aria-hidden="true">SS</div>
						<div class="ss-proposal-contact-body">
							<p class="ss-proposal-contact-name"><?php esc_html_e( 'SailScanner Team', 'sailscanner-proposals' ); ?></p>
							<p class="ss-proposal-contact-role"><?php esc_html_e( 'Charter specialists · Based in UK', 'sailscanner-proposals' ); ?></p>
							<div class="ss-proposal-contact-status">
								<span class="ss-proposal-contact-dot" aria-hidden="true"></span>
								<?php esc_html_e( 'Usually replies within 1 hour', 'sailscanner-proposals' ); ?>
							</div>
							<div class="ss-proposal-contact-btns">
								<?php if ( $contact_wa ) : ?>
									<?php
									$wa_generic = __( 'Hi, I have a question about my charter proposal.', 'sailscanner-proposals' );
									$wa_link    = SS_Proposal_Helpers::whatsapp_url( $contact_wa, $wa_generic );
									?>
									<a href="<?php echo esc_url( $wa_link ); ?>" class="ss-proposal-btn ss-proposal-btn-whatsapp" target="_blank" rel="noopener noreferrer"><?php esc_html_e( 'Chat on WhatsApp', 'sailscanner-proposals' ); ?></a>
								<?php endif; ?>
								<?php if ( $contact_email ) : ?>
									<a href="mailto:<?php echo esc_attr( $contact_email ); ?>" class="ss-proposal-btn ss-proposal-btn-outline"><?php esc_html_e( 'Email us', 'sailscanner-proposals' ); ?></a>
								<?php endif; ?>
								<?php if ( ! $contact_wa && ! $contact_email ) : ?>
									<p class="ss-proposal-muted"><?php esc_html_e( 'Contact details will be provided by your charter advisor.', 'sailscanner-proposals' ); ?></p>
								<?php endif; ?>
							</div>
							<p class="ss-proposal-contact-avail"><?php esc_html_e( 'Available Mon–Fri 9am–6pm · Weekends during peak season', 'sailscanner-proposals' ); ?><?php if ( $contact_email ) : ?> · <a href="mailto:<?php echo esc_attr( $contact_email ); ?>" class="ss-proposal-link"><?php echo esc_html( $contact_email ); ?></a><?php endif; ?></p>
						</div>
					</div>
				</div>
			</section>
		</main>
	</div>
</div>


<?php
get_footer();
