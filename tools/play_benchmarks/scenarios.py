from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayBenchmarkScenario:
    slug: str
    seed: str
    turns: list[str]


SCENARIO_SUITES: dict[str, list[PlayBenchmarkScenario]] = {
    "stability_smoke": [
        PlayBenchmarkScenario(
            slug="blind_capital",
            seed="When a lunar observatory predicts a storm that could blind the capital, a royal archivist must prove the warning is real before courtiers bury it.",
            turns=[
                "I pull the observatory warning rolls into the public archive chamber and demand the court compare them against the official forecast.",
                "I corner the chamberlain and force him to explain why the storm bulletin was delayed while the harbor shutters stayed open.",
                "I bring the observatory witnesses before the council and read the timing of the storm aloud before anyone can bury it again.",
                "I order the warning bells rung and make the court own the evacuation order in public.",
            ],
        ),
        PlayBenchmarkScenario(
            slug="ration_bridge",
            seed="A bridge engineer must keep a flood defense coalition intact after forged ration counts pit the upper wards against the river docks.",
            turns=[
                "I seize the forged ration sheets at the bridge checkpoint and compare them against the engineer corps reserve books.",
                "I gather the dock stewards and upper-ward quartermasters together and show them who altered the bridge allotments.",
                "I pressure the flood board to reopen the east span under joint supervision before the wards turn on each other.",
                "I force the coalition to sign one emergency bridge charter in front of the waiting crowds.",
            ],
        ),
        PlayBenchmarkScenario(
            slug="blackout_ombudsman",
            seed="During a blackout referendum, a city ombudsman must keep neighborhood councils from breaking apart after forged supply reports trigger panic.",
            turns=[
                "I collect the forged supply reports and question the neighborhood clerks who first repeated them during the blackout referendum.",
                "I bring the ward delegates into one room and walk them through the forged numbers line by line before panic spreads further.",
                "I go onto the public loudspeakers and explain who benefited from the fake shortages and who kept the real counts hidden.",
                "I force the councils to vote on a shared blackout ration pact before the rumor turns into open street control.",
            ],
        ),
        PlayBenchmarkScenario(
            slug="harbor_quarantine",
            seed="A tense civic fantasy about a harbor inspector preventing a port city from splintering during quarantine and supply panic.",
            turns=[
                "I inspect the harbor manifests myself and force the quarantine wardens to account for every missing shipment.",
                "I confront the trade bloc brokers with the ration discrepancies before they can turn scarcity into leverage.",
                "I bring the dock crews and city officials into one public hearing and make them hear the same inventory numbers.",
                "I force a harbor compact that keeps the port open under public oversight instead of private emergency rule.",
            ],
        ),
        PlayBenchmarkScenario(
            slug="archive_civic_record",
            seed="A hopeful civic fantasy about an archivist preserving public trust when key records are altered during an emergency vote.",
            turns=[
                "I compare the altered ledgers against the sealed archive copy and demand the clerks name who changed the record.",
                "I bring the witnesses into the records hall and test their testimony against the official transcript line by line.",
                "I read the verified chain of custody aloud to the emergency council before anyone can bury the discrepancy again.",
                "I force the city to accept one binding public record of the vote before rumor hardens into law.",
            ],
        ),
    ]
}
