# Qdrant inventory: what is on the drive

Snapshot of the **original** Qdrant (three collections, on the external drive `LAWSSD`) and the 75 parquet files, read on **2 Nov 2026**. It exists so the drive can be ejected without re-mounting it to answer a question that was already answerable. Evidence label for every number: **Measured** (read from the live system), unless a line says otherwise. Data snapshot: v2026.08.

How it was read: read-only requests, one at a time, 0.25 s apart, hard stop at 20 s. Counts come from the payload indexes (exact for small values, index counts from the facet endpoint for large ones). Nothing was written to the originals.

## 1. The collections

| Collection | Points | Status | Segments | Payload indexes | What it holds |
|---|---|---|---|---|---|
| `legal_corpus_v1` | 19,595,718 | grey (optimizer ok) | 34 | 27 | judgment chunks, all `court_type = high_court` |
| `legal_corpus_v2` | 11,823,753 | grey (optimizer ok) | 36 | 28 | judgment chunks: High Court (11,452,594) and the Supreme Court set (371,159) |
| `acts_india` | 1,098,577 | grey (optimizer ok) | 16 | 25 | Acts and regulations, one point per provision chunk |

Total points on the drive: 32,518,048. There is no `legal_corpus_v3`.

## 2. Vector configuration

| Collection | Dense vector | Sparse vector | HNSW | Quantization | Payload on disk |
|---|---|---|---|---|---|
| `legal_corpus_v1` | `dense` 1024-d Cosine, on_disk True, scalar int8 q=0.99 | `sparse` modifier idf | m=16, ef_construct=100 | on the dense vector (above) | True |
| `legal_corpus_v2` | `dense` 1024-d Cosine, on_disk True, scalar int8 q=0.99 | `sparse` modifier idf | m=16, ef_construct=100 | on the dense vector (above) | True |
| `acts_india` | `dense` 1024-d Cosine, on_disk True, scalar int8 q=0.99 | `sparse` modifier idf | m=16, ef_construct=100 | on the dense vector (above) | True |

Which model made the dense vectors (Measured on single chunks, 2 Nov 2026): a `legal_corpus_v1` High Court chunk matches `voyage-4` exactly (cosine 1.0000); Supreme Court chunks in v2 match `voyage-4-large` to about 0.999 only (20 of 20 chunks between 0.9987 and 0.9995, none exact) and one Central Act chunk matched `voyage-4-large` at 0.9994; `voyage-4` gives 0.94 to 0.96 on Supreme Court chunks. The dataset card says only "voyage-4 series". Sparse vectors are FastEmbed `Qdrant/bm25`; they reproduce for judgments but not for about half of Acts (section 8).

## 3. Payload indexes (field, type, points covered)

**`legal_corpus_v1`** (19,595,718 points)

| Field | Type | Points covered |
|---|---|---|
| `case_id` | keyword | 19,595,718 |
| `section_priority` | integer | 19,595,718 |
| `year` | integer | 19,595,718 |
| `court_type` | keyword | 19,595,718 |
| `bench_strength` | integer | 19,595,718 |
| `section_type` | keyword | 19,595,718 |
| `country_code` | keyword | 19,595,718 |
| `text` | text | 19,595,718 |
| `title` | text | 19,579,276 |
| `decision_date` | datetime | 19,534,503 |
| `petitioner` | text | 19,510,818 |
| `court` | keyword | 19,469,977 |
| `respondent` | text | 19,460,949 |
| `disposition` | keyword | 19,278,081 |
| `case_number` | keyword | 17,911,296 |
| `judges` | keyword | 7,482,370 |
| `description` | text | 2,987,959 |
| `treatment_mentions` | keyword | 590,519 |
| `state_code` | keyword | 31,250 |
| `case_type` | keyword | 0 |
| `citation` | keyword | 0 |
| `cited_by_count` | integer | 0 |
| `cases_cited` | keyword | 0 |
| `state_name` | keyword | 0 |
| `acts_referenced` | keyword | 0 |
| `bench_type` | keyword | 0 |
| `language_code` | keyword | 0 |

**`legal_corpus_v2`** (11,823,753 points)

| Field | Type | Points covered |
|---|---|---|
| `bench_strength` | integer | 11,823,753 |
| `text` | text | 11,823,753 |
| `court_type` | keyword | 11,823,753 |
| `case_id` | keyword | 11,823,753 |
| `country_code` | keyword | 11,823,753 |
| `section_type` | keyword | 11,823,753 |
| `year` | integer | 11,823,753 |
| `title` | text | 11,822,229 |
| `disposition` | keyword | 11,792,210 |
| `petitioner` | text | 11,788,319 |
| `respondent` | text | 11,784,572 |
| `court` | keyword | 11,747,967 |
| `section_priority` | integer | 11,452,594 |
| `decision_date` | datetime | 11,427,723 |
| `description` | text | 11,250,030 |
| `case_number` | keyword | 11,062,416 |
| `judges` | keyword | 4,977,739 |
| `state_code` | keyword | 1,215,927 |
| `citation` | keyword | 371,159 |
| `cited_by_count` | integer | 371,159 |
| `language_code` | keyword | 371,159 |
| `treatment_mentions` | keyword | 351,272 |
| `sparse` | keyword | 0 |
| `bench_type` | keyword | 0 |
| `cases_cited` | keyword | 0 |
| `acts_referenced` | keyword | 0 |
| `state_name` | keyword | 0 |
| `case_type` | keyword | 0 |

**`acts_india`** (1,098,577 points)

| Field | Type | Points covered |
|---|---|---|
| `act_status` | keyword | 1,098,577 |
| `chunk_id` | keyword | 1,098,577 |
| `provision_type` | keyword | 1,098,577 |
| `act_id` | keyword | 1,098,577 |
| `has_proviso` | bool | 1,098,577 |
| `amendment_count` | integer | 1,098,577 |
| `department` | keyword | 1,098,577 |
| `state` | keyword | 1,098,577 |
| `section_number` | keyword | 1,098,577 |
| `section_status` | keyword | 1,098,577 |
| `section_type` | keyword | 1,098,577 |
| `chapter` | keyword | 1,098,577 |
| `has_non_obstante` | bool | 1,098,577 |
| `country_code` | keyword | 1,098,577 |
| `legal_subject` | keyword | 1,098,577 |
| `jurisdiction` | keyword | 1,098,577 |
| `doc_type` | keyword | 1,098,577 |
| `is_repealed` | bool | 1,098,577 |
| `category` | keyword | 1,098,577 |
| `language_code` | keyword | 1,098,577 |
| `title` | text | 1,068,175 |
| `year` | integer | 934,043 |
| `acts_referenced` | keyword | 296,029 |
| `delegation_type` | keyword | 79,363 |
| `defined_terms` | keyword | 21,314 |

An index that covers 0 points exists but holds nothing (for example `language_code` on `legal_corpus_v1`). `court`, `court_type` and `case_id` are indexed on v1 and v2, so filtering and counting by them is fast; an exact count of a value that matches millions of points can still exceed 20 s.

## 4. Per-court counts (v1 and v2)

Source: the facet endpoint on the `court` index. The 56 values with 300,000 points or fewer were also counted exactly: no differences. Court names are stored as typed and include spelling variants.

**`legal_corpus_v1`**: 37 court values covering 19,469,977 points; 125,741 points have no `court` (all of them `court_type = high_court`); court_type: `high_court` 19,595,718.

| Court (as stored) | Points |
|---|---|
| Bombay High Court | 2,804,382 |
| High Court  for State of Telangana | 2,727,633 |
| Madras High Court | 2,600,953 |
| Patna High Court | 2,541,141 |
| Allahabad High Court | 1,924,170 |
| High Court Of Chhattisgarh | 1,743,234 |
| High Court of Gujarat | 1,415,395 |
| High Court of Delhi | 1,047,481 |
| High Court of Andhra Pradesh | 956,462 |
| Gauhati High Court | 656,158 |
| Calcutta High Court | 319,981 |
| High Court of Himachal Pradesh | 273,169 |
| High Court of Uttarakhand | 261,025 |
| High Court of Tripura | 138,530 |
| High Court of Patna | 21,917 |
| High Court of Bombay | 16,221 |
| High Court of Madras | 8,183 |
| High Court of Gauhati | 6,280 |
| High Court of Calcutta | 2,602 |
| High Court of Sikkim | 2,554 |
| High Court of Allahabad | 1,918 |
| High Court of Hyderabad | 462 |
| High Court of Amaravati | 42 |
| High Court of Mumbai | 27 |
| High Court of Kerala | 17 |
| High Court of Chandigarh | 9 |
| High Court of Chhattisgarh | 6 |
| High Court of Telangana | 5 |
| High Court | 3 |
| High Court of Aurangabad | 3 |
| High Court of Karnataka | 3 |
| High Court of Rajasthan | 3 |
| High Court of Andhra | 2 |
| High Court of Guwahati | 2 |
| High Court of Jabalpur | 2 |
| High Court of Chennai | 1 |
| High Court of Nagpur | 1 |
| *(no court)* | 125,741 |

**`legal_corpus_v2`**: 39 court values covering 11,747,967 points; 75,786 points have no `court` (all of them `court_type = high_court`); court_type: `high_court` 11,452,594, `supreme_court` 371,159.

| Court (as stored) | Points |
|---|---|
| High Court of Kerala | 3,125,018 |
| High Court of Karnataka | 1,552,336 |
| High Court Of Rajasthan | 1,356,011 |
| High Court of Punjab and Haryana | 1,265,076 |
| High Court of Jharkhand | 1,234,672 |
| High Court of Madhya Pradesh | 766,920 |
| Orissa High Court | 500,805 |
| High Court of Himachal Pradesh | 479,389 |
| Supreme Court of India | 371,159 |
| High Court of Jammu and Kashmir | 240,966 |
| Bombay High Court | 137,344 |
| Madras High Court | 137,003 |
| Patna High Court | 118,468 |
| High Court  for State of Telangana | 115,721 |
| High Court of Andhra Pradesh | 75,759 |
| High Court Of Chhattisgarh | 66,363 |
| High Court of Gujarat | 65,468 |
| High Court of Delhi | 45,981 |
| High Court of Manipur | 31,643 |
| Gauhati High Court | 28,669 |
| High Court of Meghalaya | 22,209 |
| Allahabad High Court | 3,462 |
| High Court of Rajasthan | 1,917 |
| High Court of Patna | 1,218 |
| High Court of Uttarakhand | 1,023 |
| Calcutta High Court | 1,002 |
| High Court of Bombay | 824 |
| High Court of Orissa | 581 |
| High Court of Madras | 379 |
| High Court of Gauhati | 282 |
| High Court of Sikkim | 124 |
| High Court of Haryana | 59 |
| High Court of Chandigarh | 45 |
| High Court of Hyderabad | 30 |
| High Court of Calcutta | 21 |
| High Court of Allahabad | 9 |
| High Court of Amaravati | 5 |
| High Court of Tripura | 5 |
| High Court of Kashmir | 1 |
| *(no court)* | 75,786 |

Spelling variants are separate values (for example "High Court of Bombay" and "Bombay High Court"; "High Court Of Rajasthan" and "High Court of Rajasthan"; "High Court  for State of Telangana" has two spaces). Merge before reporting per court.

## 5. Is v1 the same corpus as v2?

**Different mix of courts, with a partial overlap.**

- Court values only in v1 (10): High Court of Mumbai (27), High Court of Chhattisgarh (6), High Court of Telangana (5), High Court (3), High Court of Aurangabad (3), High Court of Andhra (2), High Court of Jabalpur (2), High Court of Guwahati (2), High Court of Chennai (1), High Court of Nagpur (1).
- Court values only in v2 (12): High Court Of Rajasthan (1,356,011), High Court of Punjab and Haryana (1,265,076), High Court of Jharkhand (1,234,672), High Court of Madhya Pradesh (766,920), Orissa High Court (500,805), Supreme Court of India (371,159), High Court of Jammu and Kashmir (240,966), High Court of Manipur (31,643), High Court of Meghalaya (22,209), High Court of Orissa (581), High Court of Haryana (59), High Court of Kashmir (1).
- Court values in both (27): High Court of Kerala (v1 17 / v2 3,125,018), Bombay High Court (v1 2,804,382 / v2 137,344), High Court  for State of Telangana (v1 2,727,633 / v2 115,721), Madras High Court (v1 2,600,953 / v2 137,003), Patna High Court (v1 2,541,141 / v2 118,468), Allahabad High Court (v1 1,924,170 / v2 3,462), High Court Of Chhattisgarh (v1 1,743,234 / v2 66,363), High Court of Karnataka (v1 3 / v2 1,552,336), High Court of Gujarat (v1 1,415,395 / v2 65,468), High Court of Delhi (v1 1,047,481 / v2 45,981) ....
- **Some cases are in both.** Of 200 sampled v1 cases, 13 also exist in v2; of 200 sampled v2 cases, 13 also exist in v1 (about 6.5% each way). Checked for six of each: the shared cases carry the **same chunk ids and identical text** in both collections, so it is the same content stored twice, not two versions. These are in courts that appear in both (Gujarat, Andhra Pradesh, Madras, Patna, Telangana, Bombay).
- **Duplicates inside a collection:** one shared Andhra Pradesh case has 12 chunks in v1 against 4 in v2 and a `total_chunks` of 4, and another has 6 in v1 against 3 in v2: v1 stores some chunks more than once. The Supreme Court set in v2 also has 4,871 chunk ids on two points each (392 cases).
- **Shape:** the payload fields of the two collections are almost the same (section 7). v2 has 40 distinct fields in the 10,000-point sample and v1 has 29; the fields only one of them has are listed at the end of section 7.
- Method and limit: the case sample is 100 random start ids x 100 consecutive points per collection (clusters, not independent points), so no confidence bound is given. The overlap is not a count of the whole collections.

## 6. `acts_india` breakdown (from the full scan of all 1,098,577 points)

Points 1,098,577; distinct `act_id` 22,265; parquet has 1,098,269 rows and 22,264 acts. Qdrant has 308 more points than the parquet (none the other way): regulatory +163, state +120, Central +25 (see `docs/DATASET.md`).

| Jurisdiction | Points | Acts |
|---|---|---|
| regulatory | 554,354 | 12,152 |
| state | 469,714 | 8,545 |
| central | 74,509 | 1,568 |

Parquet, by jurisdiction and instrument type (the instrument type is not in the Qdrant payload):

| Jurisdiction | Instrument type | Chunks | Acts |
|---|---|---|---|
| central | regulatory | 554,191 | 12,152 |
| state | legislation | 469,594 | 8,544 |
| central | legislation | 74,484 | 1,568 |

Regulators (points / acts): moefcc 116,227 / 1,399; rbi 104,143 / 2,640; sebi 88,310 / 1,144; law-commission 77,209 / 558; mca 46,480 / 2,666; trai 22,720 / 834; trib-ibbi 21,949 / 238; dfs 18,509 / 283; irdai 16,238 / 314; trib-gst-aar 16,025 / 75; cpcb 13,752 / 558; cbic 4,806 / 169; dgft 4,252 / 1,233; trib-cat 1,679 / 22; trib-aptel 1,258 / 7; trib-tdsat 797 / 12.

## 7. Payload field fill rates (sample of 10,000 points per collection)

Method: 100 random start ids x 100 consecutive points per collection, payload only. These are clusters, not independent points; **no confidence bound is attached**. "Non-empty" means present and not null, empty string, empty list or empty object.

**`legal_corpus_v1`**: 29 distinct payload fields in 10,000 sampled points.

| Field | Present | Non-empty |
|---|---|---|
| `bench` | 100.0% | 100.0% |
| `bench_strength` | 100.0% | 100.0% |
| `case_id` | 100.0% | 100.0% |
| `char_end` | 100.0% | 100.0% |
| `char_start` | 100.0% | 100.0% |
| `chunk_id` | 100.0% | 100.0% |
| `chunk_index` | 100.0% | 100.0% |
| `country_code` | 100.0% | 100.0% |
| `court_type` | 100.0% | 100.0% |
| `page_end` | 100.0% | 100.0% |
| `page_start` | 100.0% | 100.0% |
| `pdf_url` | 100.0% | 100.0% |
| `section_priority` | 100.0% | 100.0% |
| `section_type` | 100.0% | 100.0% |
| `text` | 100.0% | 100.0% |
| `total_chunks` | 100.0% | 100.0% |
| `year` | 100.0% | 100.0% |
| `title` | 99.9% | 99.9% |
| `decision_date` | 99.8% | 99.8% |
| `respondent` | 99.6% | 99.6% |
| `petitioner` | 99.6% | 99.6% |
| `court` | 99.5% | 99.5% |
| `description` | 99.2% | 99.2% |
| `disposition` | 98.4% | 98.4% |
| `case_number` | 91.5% | 91.5% |
| `judges` | 38.7% | 38.7% |
| `treatment_mentions` | 3.0% | 3.0% |
| `establishment_code` | 0.2% | 0.2% |
| `state_code` | 0.2% | 0.2% |

**`legal_corpus_v2`**: 40 distinct payload fields in 10,000 sampled points.

| Field | Present | Non-empty |
|---|---|---|
| `bench_strength` | 100.0% | 100.0% |
| `case_id` | 100.0% | 100.0% |
| `char_end` | 100.0% | 100.0% |
| `char_start` | 100.0% | 100.0% |
| `chunk_id` | 100.0% | 100.0% |
| `chunk_index` | 100.0% | 100.0% |
| `country_code` | 100.0% | 100.0% |
| `court_type` | 100.0% | 100.0% |
| `page_end` | 100.0% | 100.0% |
| `page_start` | 100.0% | 100.0% |
| `pdf_url` | 100.0% | 100.0% |
| `section_type` | 100.0% | 100.0% |
| `text` | 100.0% | 100.0% |
| `total_chunks` | 100.0% | 100.0% |
| `year` | 100.0% | 100.0% |
| `title` | 100.0% | 100.0% |
| `petitioner` | 99.8% | 99.8% |
| `respondent` | 99.8% | 99.8% |
| `decision_date` | 99.7% | 99.7% |
| `disposition` | 99.8% | 99.7% |
| `court` | 99.3% | 99.3% |
| `bench` | 97.1% | 97.1% |
| `section_priority` | 97.1% | 97.1% |
| `description` | 96.3% | 96.3% |
| `case_number` | 93.7% | 90.8% |
| `judges` | 41.6% | 41.6% |
| `establishment_code` | 9.8% | 9.8% |
| `state_code` | 9.8% | 9.8% |
| `treatment_mentions` | 3.2% | 3.2% |
| `citation` | 2.9% | 2.9% |
| `cited_by_count` | 2.9% | 2.9% |
| `doc_id` | 2.9% | 2.9% |
| `has_legacy_fonts` | 2.9% | 2.9% |
| `language_code` | 2.9% | 2.9% |
| `pdf_urls` | 2.9% | 2.9% |
| `scale_citation` | 0.0% | 0.0% |
| `acts_referenced` | 2.9% | 0.0% |
| `cases_cited` | 2.9% | 0.0% |
| `petitioners_all` | 2.9% | 0.0% |
| `respondents_all` | 2.9% | 0.0% |

**`acts_india`**: 71 distinct payload fields in 10,000 sampled points.

| Field | Present | Non-empty |
|---|---|---|
| `act_id` | 100.0% | 100.0% |
| `act_status` | 100.0% | 100.0% |
| `amendment_count` | 100.0% | 100.0% |
| `category` | 100.0% | 100.0% |
| `char_end` | 100.0% | 100.0% |
| `char_start` | 100.0% | 100.0% |
| `chunk_id` | 100.0% | 100.0% |
| `chunk_index` | 100.0% | 100.0% |
| `country_code` | 100.0% | 100.0% |
| `data_source` | 100.0% | 100.0% |
| `doc_type` | 100.0% | 100.0% |
| `extraction_source` | 100.0% | 100.0% |
| `has_explanation` | 100.0% | 100.0% |
| `has_illustration` | 100.0% | 100.0% |
| `has_non_obstante` | 100.0% | 100.0% |
| `has_penalty` | 100.0% | 100.0% |
| `has_proviso` | 100.0% | 100.0% |
| `has_saving_clause` | 100.0% | 100.0% |
| `is_repealed` | 100.0% | 100.0% |
| `is_subordinate` | 100.0% | 100.0% |
| `jurisdiction` | 100.0% | 100.0% |
| `language_code` | 100.0% | 100.0% |
| `legal_subject` | 100.0% | 100.0% |
| `provision_type` | 100.0% | 100.0% |
| `section_priority` | 100.0% | 100.0% |
| `section_status` | 100.0% | 100.0% |
| `section_type` | 100.0% | 100.0% |
| `state` | 100.0% | 100.0% |
| `subordinate_count` | 100.0% | 100.0% |
| `text` | 100.0% | 100.0% |
| `title` | 100.0% | 100.0% |
| `total_chunks` | 100.0% | 100.0% |
| `page_end` | 100.0% | 96.7% |
| `page_start` | 100.0% | 96.7% |
| `pdf_url` | 100.0% | 96.7% |
| `text_url` | 100.0% | 96.7% |
| `section_number` | 100.0% | 96.7% |
| `section_title` | 100.0% | 95.9% |
| `source_url` | 100.0% | 87.1% |
| `year` | 99.9% | 84.6% |
| `enactment_date` | 100.0% | 78.8% |
| `act_number` | 100.0% | 59.4% |
| `department` | 100.0% | 51.4% |
| `ministry` | 100.0% | 51.4% |
| `handle` | 100.0% | 47.3% |
| `sections_referenced_internal` | 100.0% | 43.5% |
| `chapter_title` | 100.0% | 41.9% |
| `chapter` | 100.0% | 40.5% |
| `sub_section` | 100.0% | 28.1% |
| `acts_referenced` | 100.0% | 26.8% |
| `commencement_info` | 100.0% | 26.8% |
| `part_title` | 100.0% | 25.2% |
| `part` | 100.0% | 19.0% |
| `long_title` | 100.0% | 14.8% |
| `effective_dates` | 100.0% | 10.0% |
| `delegation_type` | 100.0% | 7.4% |
| `is_current` | 6.7% | 6.7% |
| `limitation_periods` | 100.0% | 6.3% |
| `ministry_extracted` | 100.0% | 5.6% |
| `currency_note` | 5.4% | 5.4% |
| `superseded_by` | 5.4% | 5.4% |
| `territorial_extent` | 100.0% | 4.9% |
| `html_section_id` | 100.0% | 3.3% |
| `html_url` | 100.0% | 3.3% |
| `repeals` | 100.0% | 3.0% |
| `date_of_assent` | 100.0% | 2.4% |
| `defined_terms` | 100.0% | 1.8% |
| `amendment_notes` | 100.0% | 1.1% |
| `footnotes_structured` | 50.7% | 0.7% |
| `title_repaired` | 0.2% | 0.2% |
| `parent_act_id` | 100.0% | 0.0% |

Fields in the v1 sample but not the v2 sample: none. Fields in v2 but not v1: `acts_referenced`, `cases_cited`, `citation`, `cited_by_count`, `doc_id`, `has_legacy_fonts`, `language_code`, `pdf_urls`, `petitioners_all`, `respondents_all`, `scale_citation`.

## 8. The 75 parquet files

| Type | Files | Rows | Size |
|---|---|---|---|
| judgments | 26 | 32,572,660 | 53.6 GB |
| legislation | 37 | 544,078 | 0.2 GB |
| regulations | 12 | 554,191 | 0.2 GB |
| **all** | 75 | 33,670,929 | 54.0 GB |

Judgment parquet files have 31 columns, legislation and regulation files 29. Per file:

| File | Rows | Size |
|---|---|---|
| `in_allahabad_judgments.parquet` | 2,007,927 | 3.02 GB |
| `in_andaman-nicobar_legislation.parquet` | 4,626 | 0.00 GB |
| `in_andhra-pradesh_judgments.parquet` | 661,353 | 1.06 GB |
| `in_andhra-pradesh_legislation.parquet` | 12,261 | 0.00 GB |
| `in_arunachal-pradesh_legislation.parquet` | 6,993 | 0.00 GB |
| `in_assam_legislation.parquet` | 12,424 | 0.01 GB |
| `in_bihar_legislation.parquet` | 10,909 | 0.00 GB |
| `in_bombay_judgments.parquet` | 2,788,384 | 4.34 GB |
| `in_calcutta_judgments.parquet` | 535,453 | 0.73 GB |
| `in_cbic_regulations.parquet` | 4,806 | 0.00 GB |
| `in_central_legislation.parquet` | 74,484 | 0.03 GB |
| `in_chandigarh_legislation.parquet` | 21,790 | 0.01 GB |
| `in_chhattisgarh_judgments.parquet` | 1,744,438 | 2.57 GB |
| `in_chhattisgarh_legislation.parquet` | 25,363 | 0.01 GB |
| `in_cpcb_regulations.parquet` | 13,750 | 0.00 GB |
| `in_dadra-nagar-haveli_legislation.parquet` | 15,618 | 0.01 GB |
| `in_delhi_judgments.parquet` | 1,064,459 | 1.99 GB |
| `in_delhi_legislation.parquet` | 8,003 | 0.00 GB |
| `in_dfs_regulations.parquet` | 18,509 | 0.01 GB |
| `in_dgft_regulations.parquet` | 4,252 | 0.00 GB |
| `in_gauhati_judgments.parquet` | 663,094 | 1.14 GB |
| `in_goa_legislation.parquet` | 14,535 | 0.00 GB |
| `in_gujarat_judgments.parquet` | 1,400,249 | 2.25 GB |
| `in_gujarat_legislation.parquet` | 12,866 | 0.00 GB |
| `in_haryana_legislation.parquet` | 11,784 | 0.00 GB |
| `in_himachal-pradesh_judgments.parquet` | 619,919 | 1.01 GB |
| `in_himachal-pradesh_legislation.parquet` | 10,762 | 0.00 GB |
| `in_irdai_regulations.parquet` | 16,236 | 0.01 GB |
| `in_jammu-and-kashmir_judgments.parquet` | 181,221 | 0.26 GB |
| `in_jammu-kashmir_legislation.parquet` | 9,220 | 0.00 GB |
| `in_jharkhand_judgments.parquet` | 777,734 | 1.11 GB |
| `in_jharkhand_legislation.parquet` | 10,829 | 0.00 GB |
| `in_karnataka_judgments.parquet` | 1,471,128 | 2.94 GB |
| `in_karnataka_legislation.parquet` | 29,479 | 0.01 GB |
| `in_kerala_judgments.parquet` | 2,777,738 | 4.56 GB |
| `in_kerala_legislation.parquet` | 19,156 | 0.01 GB |
| `in_ladakh_legislation.parquet` | 3,114 | 0.00 GB |
| `in_lakshadweep_legislation.parquet` | 171 | 0.00 GB |
| `in_law-commission_regulations.parquet` | 77,080 | 0.04 GB |
| `in_madhya-pradesh_judgments.parquet` | 970,908 | 1.49 GB |
| `in_madhya-pradesh_legislation.parquet` | 17,465 | 0.01 GB |
| `in_madras_judgments.parquet` | 2,610,596 | 4.62 GB |
| `in_maharashtra_legislation.parquet` | 30,264 | 0.01 GB |
| `in_manipur_judgments.parquet` | 39,507 | 0.06 GB |
| `in_manipur_legislation.parquet` | 4,559 | 0.00 GB |
| `in_mca_regulations.parquet` | 46,477 | 0.02 GB |
| `in_meghalaya_judgments.parquet` | 25,558 | 0.04 GB |
| `in_meghalaya_legislation.parquet` | 5,549 | 0.00 GB |
| `in_mizoram_legislation.parquet` | 2,015 | 0.00 GB |
| `in_moefcc_regulations.parquet` | 116,227 | 0.04 GB |
| `in_nagaland_legislation.parquet` | 4,861 | 0.00 GB |
| `in_odisha_legislation.parquet` | 11,369 | 0.00 GB |
| `in_orissa_judgments.parquet` | 872,833 | 1.03 GB |
| `in_patna_judgments.parquet` | 2,562,269 | 3.68 GB |
| `in_puducherry_legislation.parquet` | 7,117 | 0.00 GB |
| `in_punjab-and-haryana_judgments.parquet` | 1,845,344 | 2.31 GB |
| `in_punjab_legislation.parquet` | 18,034 | 0.01 GB |
| `in_rajasthan_judgments.parquet` | 2,676,195 | 4.00 GB |
| `in_rajasthan_legislation.parquet` | 26,756 | 0.01 GB |
| `in_rbi_regulations.parquet` | 104,122 | 0.05 GB |
| `in_sebi_regulations.parquet` | 88,310 | 0.03 GB |
| `in_sikkim_judgments.parquet` | 11,389 | 0.02 GB |
| `in_sikkim_legislation.parquet` | 4,266 | 0.00 GB |
| `in_state-gst_regulations.parquet` | 41,702 | 0.01 GB |
| `in_supreme-court_judgments.parquet` | 1,113,313 | 3.76 GB |
| `in_tamil-nadu_legislation.parquet` | 15,522 | 0.01 GB |
| `in_telangana_judgments.parquet` | 2,732,387 | 4.92 GB |
| `in_telangana_legislation.parquet` | 16,783 | 0.00 GB |
| `in_trai_regulations.parquet` | 22,720 | 0.01 GB |
| `in_tripura_judgments.parquet` | 112,120 | 0.18 GB |
| `in_tripura_legislation.parquet` | 8,069 | 0.00 GB |
| `in_uttar-pradesh_legislation.parquet` | 14,299 | 0.00 GB |
| `in_uttarakhand_judgments.parquet` | 307,144 | 0.44 GB |
| `in_uttarakhand_legislation.parquet` | 10,525 | 0.00 GB |
| `in_west-bengal_legislation.parquet` | 32,238 | 0.01 GB |

## 9. What exists only on the drive, and what is in the copies

- **Only on the drive:** all three original collections (31.4M judgment points and 1.1M Acts points, 32.5M in total, with their vectors) and the 54 GB of parquet. The data copy on the internal disk (`kanoon_v1`, port 7333) holds 445,643 points: the 371,159 Supreme Court chunks from v2 (a verified, complete copy of that set) and 74,484 Central Act points. `acts_sample_v1` holds a 10,000-point sample of other Acts. Nothing else was copied: High Court chunks (about 31M) and the state and regulatory Acts (about 1.02M) exist only on the drive.
- **Text for High Court chunks is present and embedded:** v1 and v2 High Court points carry the chunk text, a 1024-d dense vector and a sparse vector (checked on three points from each).

## 10. Known data issues (details in the cited files)

- **Sparse (keyword) vectors:** wrong for 19,835 of 74,509 Central Act points (26.6%, full scan) and 49.4% of a 10,000-point sample of the other Acts (Estimate: about 524,000 of 1,098,577 overall). They are raw term counts, not BM25 weights. Judgment sparse vectors reproduce. A repair script was tested on the sample and applied to the 19,830 Central points in the copy; the originals are untouched.
- **Parquet and Qdrant are different cuts:** for the Supreme Court set, 10,112 English chunks (749 cases) are only in the parquet, 5,153 only in Qdrant, and 4,871 chunk ids sit on two points each. For Acts, Qdrant has 308 extra points. Cause unverified.
- **Court names:** variants and a missing `court` on 125,741 v1 and 75,786 v2 points (all High Court by `court_type`).
- **Text quality:** replacement characters in the text of 5.4% of a regulatory sample and 1.6% of a state sample.
- **Supreme Court translations:** 742,066 vernacular-labelled chunks are in the parquet only; none is in Qdrant.

## 11. Not verified, and how to refresh

- Exact (not index) counts for the largest court values; per-court counts of distinct cases; the share of v1 and v2 cases that overlap across the whole collections; which embedding model made each Act's vectors; whether the stored vectors can be reproduced exactly.
- Refresh needs the drive mounted and the Qdrant container running on `localhost:6333`. The scripts that produced these numbers are in the working session's scratchpad (`part6_collect.py`, `part1_*.py`); the raw JSON is in `~/qdrant-kanoon/reports/` (`part6_inventory.json`, `part1_acts_counts.json`).
