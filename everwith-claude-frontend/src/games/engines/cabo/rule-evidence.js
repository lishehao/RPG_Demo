// This is evidence metadata, not permission to treat unverified components as official.
export const RULE_EVIDENCE=Object.freeze({
 target:'Shareful Games 2025 English publication',
 baseline:'current-shareful-public-standard-rules',
 procedureSource:'https://www.cabogame.com/how-to-play',
 productSource:'https://www.cabogame.com/buy-cabo/p/cabo-card-game',
 publisherSource:'https://www.cabogame.com/about-shareful-games-llc',
 checkedAt:'2026-10-07',
 procedures:'publisher-web-text-checked',
 procedureScope:Object.freeze({
  officialExplicit:Object.freeze(['initial-four-cards-two-private-peeks','exchanges-face-down','failed-match-show-return-discard-drawn','failed-caller-plus-five','retain-discard-top-and-reshuffle','shooting-the-moon','first-exact-100-reset-game-ends-above-100']),
  contextInterpretation:Object.freeze(['caller-priority-in-lowest-tie-other-tied-players-score-hand-sum']),
  implementationConventions:Object.freeze(['final-total-ties-share-victory','next-starter-clockwise-from-previous-starter-among-minimum-round-gains','failed-match-return-face-down','reshuffle-immediately-after-last-deck-draw']),
  pendingReview:Object.freeze(['zero-round-gain-can-select-non-winner-labelled-next-starter','no-recyclable-discard-remainder']),
 }),
 totalCards:52,
 numberRange:Object.freeze([0,13]),
 totalAndRange:'publisher-product-text-checked',
 playerRange:Object.freeze([2,5]),
 playerRangeEvidence:'publisher-product-text-checked',
 chineseEdition:'not-verified',
 components:'not-verified-from-current-physical-cards',
 abilityNumbers:'legacy-component-hypothesis',
 abilityComparison:Object.freeze({
  status:'matches-bezier-primary-rules-not-shareful-certified',
  sharefulVerified:false,
  sources:Object.freeze(['https://cdn.shopify.com/s/files/1/0740/4855/files/Cabo-online-rules.jpg?6346435320125113992=','https://cdn.shopify.com/s/files/1/0740/4855/files/CABX_Cabo_Deluxe_Edition_rules.pdf?443=']),
 }),
 distribution:'legacy-component-hypothesis',
 completePhysicalRulesVerified:false,
});
export const PROVISIONAL_COMPONENT_PROFILE=Object.freeze({
 name:'legacy-component-hypothesis',verified:false,
 abilities:Object.freeze({7:'peek',8:'peek',9:'spy',10:'spy',11:'swap',12:'swap'}),
 counts:Object.freeze(Array.from({length:14},(_,v)=>v===0||v===13?2:4)),
});
export const ability=v=>PROVISIONAL_COMPONENT_PROFILE.abilities[v]||null;
