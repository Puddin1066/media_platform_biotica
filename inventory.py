"""Honest inventory of what exists — not a claim that it all works end-to-end."""

INVENTORY = {
    'intended_product': {
        'name': 'One pipeline per media piece',
        'should_be': 'web search → narrative → finished media file',
        'actually_is': (
            'pipeline.py can dry-run: theme → research memo → script draft → '
            'Runway job *plans* → review gate. It does not yet deliver a finished '
            'MP4/audio file you can play.'
        ),
        'status': 'half_baked',
        'entry': 'python3 ui_server.py  OR  python3 pipeline.py start --format short',
    },
    'pieces': [
        {
            'id': 'pipeline',
            'name': 'Step orchestrator',
            'file': 'pipeline.py',
            'role': 'Chains stages for one run',
            'status': 'usable_dry_run',
            'baked': 'Theme → research → writing → media *plans* → review',
            'missing': 'No single “make the short” button that finishes media; live spend needs budgets; host plate MP4 often missing',
        },
        {
            'id': 'produce',
            'name': 'Web-search → script',
            'file': 'produce.py',
            'role': 'Closest to “search then write narrative”',
            'status': 'usable_dry_run_live_gated',
            'baked': 'OpenAI Responses + web_search → five-beat script JSON/MD',
            'missing': 'Stops at text; not a finished short video',
        },
        {
            'id': 'web_research',
            'name': 'Web-search memos only',
            'file': 'web_research.py',
            'role': 'Discovery without drafting',
            'status': 'usable_dry_run_live_gated',
            'baked': 'Per-hypothesis search memos + citations',
            'missing': 'Not a narrative; separate from produce',
        },
        {
            'id': 'writer',
            'name': 'Write from cleared claims',
            'file': 'writer.py',
            'role': 'Older path — no web search',
            'status': 'side_path',
            'baked': 'Narrates a pre-reviewed claim packet',
            'missing': 'Does not search the web; seed case has no reviewed claims',
        },
        {
            'id': 'research_pmc',
            'name': 'Europe PMC literature',
            'file': 'research.py',
            'role': 'Optional specialist search',
            'status': 'side_path',
            'baked': 'Abstract snapshots + review templates',
            'missing': 'Not the primary path; not narrative; not media',
        },
        {
            'id': 'analyst',
            'name': 'Abstract triage',
            'file': 'analyst.py',
            'role': 'Optional model suggestions on abstracts',
            'status': 'side_path',
            'baked': 'Mock-tested OpenAI triage',
            'missing': 'Not required for shorts; human-review only',
        },
        {
            'id': 'studio_export',
            'name': 'Offline planning briefs',
            'file': 'studio.py + exporter.py',
            'role': 'Validate case; emit blocked outlines',
            'status': 'complete_for_offline_preview',
            'baked': 'Deterministic JSON/MD planning packets',
            'missing': 'No AI, no media, explicitly blocked from publish',
        },
        {
            'id': 'runway',
            'name': 'Runway media planner',
            'file': 'runway.py',
            'role': 'Plans speech/video/plate jobs',
            'status': 'half_baked',
            'baked': 'Builds request bodies; dry-run; live gate; Peloton plate path',
            'missing': 'No reliable poll→download→finished asset package in-repo',
        },
        {
            'id': 'short_prompts',
            'name': 'Short boilerplate prompts',
            'file': 'prompts/short.py',
            'role': 'Beats + narrator + visual/speech boilerplates',
            'status': 'usable',
            'baked': 'short-pack-1 wired into produce + runway when format=short',
            'missing': 'A pack is not a pipeline by itself',
        },
        {
            'id': 'costs',
            'name': 'Cost estimates',
            'file': 'costs.py',
            'role': 'Token/USD planning numbers',
            'status': 'usable',
            'baked': 'Estimates + dry-run actual=$0',
            'missing': 'Not a provider invoice',
        },
        {
            'id': 'ui',
            'name': 'Operator UI',
            'file': 'ui_server.py',
            'role': 'Browser front for the orchestrator',
            'status': 'usable_but_noisy',
            'baked': 'Step buttons, cost panel, plate status',
            'missing': 'Shows the fragmentation; does not hide it',
        },
    ],
}


def summary():
    counts = {}
    for piece in INVENTORY['pieces']:
        counts[piece['status']] = counts.get(piece['status'], 0) + 1
    return {
        'intended': INVENTORY['intended_product'],
        'piece_count': len(INVENTORY['pieces']),
        'status_counts': counts,
        'pieces': INVENTORY['pieces'],
        'pragmatic_answer': (
            'There is effectively ONE intended pipeline (pipeline.py + UI), '
            'plus about half a dozen side modules left over from earlier slices. '
            'None of them yet end in a finished playable short. The closest '
            '“press a button” path is: start a short run → advance through '
            'research/writing → get a script + Runway *plans*. Media file output '
            'is still unfinished.'
        ),
    }
