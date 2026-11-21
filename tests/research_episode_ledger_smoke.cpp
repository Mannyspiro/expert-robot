#include "expert_robot/research/episode_ledger.hpp"
#include "expert_robot/research/state_machine.hpp"

#include <sqlite3.h>

#include <cassert>
#include <filesystem>
#include <string>

int main() {
    using namespace expert_robot::research;

    const auto db =
        std::filesystem::temp_directory_path() /
        "expert-robot-research-episode.sqlite3";
    std::filesystem::remove(db);

    ResearchEpisodeLedger ledger(db);
    ResearchStateMachine machine;

    const std::string episode =
        "episode-001";

    const auto intake_event =
        ledger.append(
            episode,
            "episode_started",
            "goal=prove target theorem");
    assert(intake_event.sequence == 0);
    assert(intake_event.previous_event_hash.empty());
    assert(!intake_event.event_hash.empty());

    auto transition =
        machine.step(
            ResearchObservation{});
    const auto transition_event =
        ledger.append_transition(
            episode,
            transition,
            machine.state());
    assert(transition_event.sequence == 1);
    assert(
        transition_event.previous_event_hash ==
        intake_event.event_hash);

    ResearchObservation retrieved;
    retrieved.retrieval_complete = true;
    transition =
        machine.step(retrieved);
    const auto direct_event =
        ledger.append_transition(
            episode,
            transition,
            machine.state());
    assert(direct_event.sequence == 2);

    const auto failure_event = ledger.append_failure_observation(
        episode,
        FailureObservation{
            .source_agent = "hermes",
            .source_task_id = "hermes-task-0001",
            .stage = "lean_proof",
            .failure_class = "proof_search_exhausted",
            .target_sha256 = std::string(64, 'a'),
            .diagnostic_sha256 = std::string(64, 'b'),
            .attempt_count = 3,
        });
    assert(failure_event.sequence == 3);
    assert(failure_event.event_type == "failure_observation.v1");
    assert(failure_event.payload.find("\"source_agent\":\"hermes\"") != std::string::npos);
    assert(failure_event.payload.find("\"attempt_count\":3") != std::string::npos);

    const auto verified =
        ledger.verify(episode);
    assert(verified.valid);
    assert(verified.event_count == 4);
    assert(verified.first_invalid_sequence == -1);
    assert(
        verified.root_hash ==
        failure_event.event_hash);

    const auto events =
        ledger.events(episode);
    assert(events.size() == 4);
    assert(events[0].sequence == 0);
    assert(events[1].sequence == 1);
    assert(events[2].sequence == 2);
    assert(events[3].event_type == "failure_observation.v1");

    // Separate episodes have separate chains.
    const auto other =
        ledger.append(
            "episode-002",
            "episode_started",
            "goal=another theorem");
    assert(other.sequence == 0);
    assert(other.previous_event_hash.empty());
    const auto other_verified =
        ledger.verify("episode-002");
    assert(other_verified.valid);
    assert(other_verified.event_count == 1);
    assert(other_verified.root_hash == other.event_hash);

    // Simulate an out-of-band edit of immutable history.
    sqlite3* raw = nullptr;
    assert(
        sqlite3_open(
            db.string().c_str(),
            &raw) == SQLITE_OK);

    char* error = nullptr;
    int rc = sqlite3_exec(
        raw,
        "UPDATE research_episode_events "
        "SET payload='tampered payload' "
        "WHERE episode_id='episode-001' AND sequence=1;",
        nullptr, nullptr, &error);
    if (error != nullptr) sqlite3_free(error);
    error = nullptr;
    assert(rc != SQLITE_OK);

    rc = sqlite3_exec(
        raw,
        "DELETE FROM research_episode_events "
        "WHERE episode_id='episode-001' AND sequence=1;",
        nullptr, nullptr, &error);
    if (error != nullptr) sqlite3_free(error);
    error = nullptr;
    assert(rc != SQLITE_OK);
    assert(ledger.verify(episode).valid);

    // Demonstrate that the hash chain still detects tampering if a database
    // administrator deliberately removes the immutability trigger.
    rc = sqlite3_exec(
        raw,
        "DROP TRIGGER research_episode_events_no_update;"
        "UPDATE research_episode_events SET payload='tampered payload' "
        "WHERE episode_id='episode-001' AND sequence=1;",
        nullptr, nullptr, &error);
    if (error != nullptr) sqlite3_free(error);
    assert(rc == SQLITE_OK);
    sqlite3_close(raw);

    const auto tampered =
        ledger.verify(episode);
    assert(!tampered.valid);
    assert(tampered.first_invalid_sequence == 1);
    assert(tampered.reason == "payload hash mismatch");

    std::filesystem::remove(db);
    return 0;
}
