# Historical prologue guarantee — P3

[Español](prologue-navigation.es.md). Implemented:
`historical-prologue-chain-v1`, an extension of `historical-world-v1` and
`historical-information-v1`. This is not a saved-game migration.

## Construction and proof

`worldgen/narrative.prepare_new_world` compiles the catalog and its essential
narrative reservations before reserving this chain. `manifest.reserve_prologue`
examines exactly the nine generation cohorts in ECHO_7's initial neighborhood.
A stable hash of seed and identity selects a procedural site with
`salvage_data`, free of reservations/protections, at positive distance and no
more than 45 ly from either anchor. ARCHIVE_01, like every authored site, is
outside this selection.

If the admissible set is empty, one extra procedural `derelict` slot is added
to the initial manifest. With the installed anchors ECHO_7=(0,0,0) and
HARBOR_12=(12,4,0), its seed-derived position belongs to
`[4,6) × [1,3) × [0.1,0.2)`, using a local RNG. This entire volume lies strictly
inside both 45 ly balls and excludes the anchors. This inequality and the
exhaustive alternative “admissible candidate / empty set” establish the guarantee
for every valid seed; sample seeds are not its proof.

The slot takes the next free procedural index in its cohort. It is appended
after ordinary sites, hubs and edges have been sampled; their draws, identities
and connections stay unchanged. It needs no historical physical edge: both hops
may be calculated navigation solutions. Identity lookup, inverse physical
inventory and normal materialization use the same manifest. The reservation is
fixed before exploration and does not depend on visit order.

A catalog with incompatible anchors or restrictions is rejected without
changing seeds, relaxing protections or accepting a partial guarantee. This
box does not claim compatibility with arbitrary anchor positions.

## Public acquisition and preservation

`information.query_information` first completes ordinary selection and applies
P1. If the intermediary is absent, its record is appended to ECHO_7's uplink;
if there are already three destinations, only the last is replaced. An already
selected intermediary leaves the list unchanged. No direct HARBOR_12 route
fills a slot and authored documents are not modified.

The intermediary contains `/data/nav/waystation_solution.txt`, with `guest` access,
a typed B1 record and the existing renderer's bilingual content:
`LINK: P -> HARBOR_12`. It is a base archive recoverable through ordinary
`dock`, `drone deploy`, `drone salvage data`, reading and import. It depends on
no scheduler windows, file rolls, radio or later recovery. The incoming route
is acquired by uplinking at ECHO_7. The player still needs to travel, recover
the data and read it to use the second route.

The additional slot is excluded from ordinary weighted pools to avoid
reordering existing histories; its incoming record is the explicit reservation.
B2 queries B1 without either new reservation. Its ordinary pool and draws stay
unchanged, existing alternative clues remain allowed, and the additional wreck
declares no radio equipment. Thus the new guarantee cannot produce an emission
receivable at ECHO_7 carrying the reserved HARBOR_12 LINK.

## Contract and certification

`ManifestDefinition` captures the version, chosen identity, initial exclusions
and optional fallback slot. `InformationDefinition.prologue_json` captures the
version and host and participates in the full information fingerprint; its
sampling projection preserves the ordinary B1 fingerprint. B2 binds that full
fingerprint but uses ordinary sampling. The physical extension preserves the
scope of previous identities. Changes to these rules require an explicit
extension version change.

`information.certify_prologue` runs during preparation and save/load: it
reconstructs physical selection and checks identity, distances, restrictions,
interfaces, the effective uplink record, the three-destination limit, absence
of a direct procedural route, and a readable/importable base archive. The first
clue is at ECHO_7; the second is at the destination enabled by that first clue:
there is no circular dependency. Certification imports no intel, activates no
pools, consumes no RNG and changes no clock. Older saves with these anchors but
without this contract are rejected.

Focused verification: `tests/prologue_chain_smoke.py`. Covers 1/29/701, P1
exclusions, controlled fallback, physical inventory/materialization, negative
certificates, hidden-state nondisclosure in status, B2, FAST_SANDBOX,
salvage/read/import EN/ES, save/load and a public journey. It also preserves
the alternative two-uplink journey previously observed in seed 1.

Commands, help and diegetic manuals are unchanged: existing flows apply and
these texts should not disclose the secret reservation. Survival, physical
times, lore, god mode and prologue completion criteria are unchanged.
