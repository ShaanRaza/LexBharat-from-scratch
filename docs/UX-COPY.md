# User-facing copy and states

The exact wording the product shows. These strings carry the trust promise and the legal
position, so **do not improvise them in code**. Keep them in one place, versioned, and
change them deliberately.

Headline and marketing copy are **not** here — the headline is still a placeholder.

## Failure and edge states

Every one of these must exist before launch. "Nothing is guessed" is the rule in all of
them.

| Situation | What the user sees | What it costs |
|---|---|---|
| **No relevant results** | "No matching judgments found in our dataset (data as of the snapshot date)." Plus suggestions to rephrase or use Act lookup. **No written answer is generated, so nothing is invented** | One search call, no LLM call |
| **Voyage API is down** | A notice that meaning-based search is unavailable. Act lookup, outcome statistics and keyword search still work and are labelled **"keyword results only"**. A retry button | No Voyage call |
| **A judgment is longer than the model can read** | "This judgment is too long to read in full. Answering from the most relevant parts." The parts used are listed, and the user can ask about a page range | Needs verification: measure the longest judgments against the model's limit |
| **An upload is an unreadable scan** | "We could not read this file. Try a clearer scan or paste the text." Nothing is guessed. **The usage meter is not charged** | OCR attempt only |
| **The dataset has no coverage of the question** | <!-- coverage-sentence:begin -->"LexBharat covers Supreme Court judgments and the Central Acts listed on our coverage page. It does not include High Courts, district courts, tribunals, or anything after the data-as-of date." **NEEDS-OWNER** (generated from `core/coverage.json`)<!-- coverage-sentence:end --> Points to the official court site. A question about a source the dataset does not hold (for example an Act that is not listed) gets the O7 message instead: "not in our dataset" (`message_key` `out_of_scope:not_in_dataset`), never "does not exist" | No LLM call if detected early |
| **The LLM provider fails or times out** | The retrieved sources are shown **with links but no written answer**, and the user can retry | Retrieval cost only |
| **The verifier rejects a cited authority** | The answer is shown with that citation removed and a note saying one authority could not be verified. The failure is written to `invented_citation_log` | Free |

## The verification badge

**Shown wording:** "Record found in dataset", with the data-as-of date and a short link to
the definition.

- **Tick** = the passage supports the sentence.
- **Warning mark** = it supports it only partly.
- Anything that fails = removed, or marked **"Not verified"**.
- **Per citation, never one badge for the whole answer.**

Full "means / does not mean" table: [CITATION-VERIFIER.md](CITATION-VERIFIER.md).

## Standing notices

| Where | Notice |
|---|---|
| Every answer, stats page and Act page | KanoonBuddy gives **information, not legal advice** |
| When Jev's safety check flags a personal-advice question | The answer **opens** by saying it cannot advise on the user's own situation, and suggests consulting an advocate |
| Every result, stats page, Act page and share card | The **data-as-of date** |
| Every result, stats page, Act page and share card | `Data: Open India Law by Vaquill AI, CC BY 4.0` |
| An Act whose `act_status`, `is_repealed`, `IND_REP_` id or title marker says repealed | **"Repealed"** (A180, A181) |
| An Act whose `act_status` says in force and nothing says repealed | **"In force"** only if the owner sets `SHOW_IN_FORCE`; **off** until the act_status count is in (A181) |
| Every other Act result, including one with an unclear repeal note in its title | **"In-force status not checked for this Act."** |
| Before upload | A warning about privileged material |
| Answers from courts whose records carry no citation string (none in v1; later phases) | No citation string is shown — `citation` is 0.0% filled for those courts |

## Copy rules

- **Plain words.** The audience includes students and the general public, not only lawyers.
- Sample content is labelled **"Sample"**.
- **Never name an advocate** on any page, share card or statistic (BCI Rule 36).
- **Never show judge or party names** — those fields failed the audit.
- Outcome statistics are **descriptive**. Never "likely to win", "chances" or any prediction.
- No customer logos, testimonials, uptime or security claims until they exist.
- Competitors are not named in product copy.
- Usage limits are shown as **plain numbers** ("100 research answers a month"), never credits.

## Consent and legal documents

The consent notice is **versioned** — `consents.notice_version` in the database points at a
specific document. Those documents live in [`../legal/`](../legal/) and must exist before
sign-up works.
