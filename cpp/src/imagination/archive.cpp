#include "expert_robot/imagination/archive.hpp"

#include <algorithm>
#include <cctype>
#include <set>
#include <stdexcept>
#include <string>

namespace expert_robot::imagination {
namespace {

std::set<std::string> tokens(std::string_view text) {
    std::set<std::string> result;
    std::string current;

    auto flush = [&]() {
        if (current.size() >= 2U) result.insert(current);
        current.clear();
    };

    for (unsigned char ch : text) {
        if (std::isalnum(ch) || ch == '_') {
            current.push_back(
                static_cast<char>(std::tolower(ch)));
        } else {
            flush();
        }
    }
    flush();
    return result;
}

double jaccard(
    const std::set<std::string>& a,
    const std::set<std::string>& b) {
    if (a.empty() && b.empty()) return 1.0;
    if (a.empty() || b.empty()) return 0.0;

    std::size_t intersection = 0;
    auto ia = a.begin();
    auto ib = b.begin();

    while (ia != a.end() && ib != b.end()) {
        if (*ia == *ib) {
            ++intersection;
            ++ia;
            ++ib;
        } else if (*ia < *ib) {
            ++ia;
        } else {
            ++ib;
        }
    }

    const std::size_t uni =
        a.size() + b.size() - intersection;
    return uni == 0U
        ? 1.0
        : static_cast<double>(intersection) /
              static_cast<double>(uni);
}

bool better(
    const IdeaCandidate& a,
    const IdeaCandidate& b) {
    if (a.quality_diversity_score !=
        b.quality_diversity_score) {
        return a.quality_diversity_score >
               b.quality_diversity_score;
    }
    if (a.novelty_score != b.novelty_score) {
        return a.novelty_score > b.novelty_score;
    }
    return a.idea_id < b.idea_id;
}

} // namespace

double textual_novelty(
    std::string_view candidate,
    const std::vector<std::string>& references) {
    if (references.empty()) return 1.0;

    const auto candidate_tokens = tokens(candidate);
    double max_similarity = 0.0;

    for (const auto& reference : references) {
        max_similarity = std::max(
            max_similarity,
            jaccard(candidate_tokens, tokens(reference)));
    }

    return std::clamp(
        1.0 - max_similarity,
        0.0,
        1.0);
}

QualityDiversityArchive::QualityDiversityArchive(
    std::size_t capacity_per_lens)
    : capacity_per_lens_(capacity_per_lens) {
    if (capacity_per_lens_ == 0U) {
        throw std::invalid_argument(
            "quality-diversity archive capacity must be positive");
    }
}

double QualityDiversityArchive::novelty_score(
    std::string_view text) const {
    std::vector<std::string> references;
    for (const auto& [lens, candidates] : niches_) {
        (void)lens;
        for (const auto& candidate : candidates) {
            references.push_back(candidate.text);
        }
    }
    return textual_novelty(text, references);
}

void QualityDiversityArchive::insert(
    IdeaCandidate candidate) {
    auto& niche = niches_[candidate.lens];

    const auto duplicate = std::find_if(
        niche.begin(),
        niche.end(),
        [&](const IdeaCandidate& existing) {
            return existing.idea_id == candidate.idea_id;
        });

    if (duplicate != niche.end()) {
        if (better(candidate, *duplicate)) {
            *duplicate = std::move(candidate);
        }
    } else {
        niche.push_back(std::move(candidate));
    }

    std::stable_sort(
        niche.begin(),
        niche.end(),
        better);

    if (niche.size() > capacity_per_lens_) {
        niche.resize(capacity_per_lens_);
    }
}

std::vector<IdeaCandidate>
QualityDiversityArchive::elites(
    ImaginationLens lens) const {
    const auto it = niches_.find(lens);
    if (it == niches_.end()) return {};
    return it->second;
}

std::vector<IdeaCandidate>
QualityDiversityArchive::all_elites() const {
    std::vector<IdeaCandidate> result;
    for (const auto& [lens, candidates] : niches_) {
        (void)lens;
        result.insert(
            result.end(),
            candidates.begin(),
            candidates.end());
    }
    std::stable_sort(
        result.begin(),
        result.end(),
        better);
    return result;
}

std::size_t QualityDiversityArchive::size() const noexcept {
    std::size_t total = 0;
    for (const auto& [lens, candidates] : niches_) {
        (void)lens;
        total += candidates.size();
    }
    return total;
}

} // namespace expert_robot::imagination
