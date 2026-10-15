# MANIFEST — submission version 2026-10-16b (Computer Law & Security Review)

Analysis version frozen 2026-10-16, second cut (R-2026-10-16-2: agreement-table scoring scope, constant-predictor κ, l2_agreement.py, openpyxl dependency, table7 marked superseded; supersedes 2026-10-15: matching-sensitivity tables, evidence links in the 20-case label file, κ relabelling in the re-test script, document-property anonymization, reproduction fixes; see `docs/deviation_log.md` R-2026-10-16-1). Labels and panel outputs date from 2026-08-15 (calibration) / 2026-08-18 registration / post-registration analyses 2026-09-16. SHA-256 over repository contents at this commit.

**Distribution copies.** The anonymous reviewer mirror is generated from this repository with term redaction (author identity, preregistration identifier, archive identifiers, the §6.4 case numbers and court). After the 2026-10-16 regeneration every file listed here is expected to hash identically in the mirror, because no analysis file contains a redacted term; a mismatch would indicate that the redaction touched a data file and is reported in the submission notes rather than silently accepted.

| path | role | sha256 |
|---|---|---|
| `.gitignore` |  | `6dfa268173c6168661506170c0f98942f3984562b17342dc432dabed43dc79cb` |
| `LICENSE` |  | `6829857579b354e14c4582f8bf9e1cd170d041258a973e59933095adedb7c1ad` |
| `README.md` | overview | `16459bde7f5c11ab52242366bfcd72f92bd1c3606a09489166acc7c2f5e64583` |
| `REPRODUCE.md` | number-by-number reproduction | `bda92041930a009a4ca2006bd215d8b653cb48c7ac3f70b9a2bf654250925c8f` |
| `codebook/annotation_guideline.md` |  | `0182fd1e9d796b46cfafc757e26a1f3caeaf3a5fdc61a6df03b7566b1f56774a` |
| `data/labels/claim_check_labeled.csv` | Table 4 labels (current; evidence links added 2026-10-16) | `edbe2ae9f58ae1169d26ec17cdb03e5c78fd1285e853483ea1465b6845125b14` |
| `data/labels/claim_check_labeled_v1_superseded.csv` | Table 4 labels (superseded 2026-09-16) | `92c5d785d6a603514641a5c43ff70055843fd2abe2cf1708bc4e5b01478ba699` |
| `data/labels/external_claims_resolution.csv` |  | `6a9a5d525344c7a348dd11068c2e6b786026d2d734b1effead28427d8e2ba846` |
| `data/labels/findings_D1_triage_v2.csv` |  | `fbe9a6db4f7f6746e317014260be351b4ed0728b171bbd60d62a1c93eb2c2dad` |
| `data/labels/findings_D1_triage_v3.csv` |  | `6c9a9ef1fcfb12f871b9d163d89113138d9b406bf8bbf61953106e3944698283` |
| `data/labels/goldset_labeled_v2.csv` |  | `913957a72035c70e9510bd5ed932ba73c3ad2da165576788ac233f19772ae3ef` |
| `data/labels/goldset_llm.csv` |  | `9ced981adea2137f2aa0e6e099a1df054b5bb561cff740fd733a9e061b92393c` |
| `data/labels/goldset_retest_0818.csv` |  | `f5ce3fbe6f7e63782d070490c69ced70de9a759e84a0c7c6f6a439530f8bffa8` |
| `data/labels/goldset_retest_sept.xlsx` | re-test workbook (document-property author field blanked 2026-10-16; cells unchanged) | `e58a007726126a46fd535b857357049cfd4bf50f28f1cca14f041a56fb387325` |
| `data/labels/goldset_retest_sept_blank.csv` |  | `136b24d102d2566c1e5b7a1701e0bac38d067b247734fcd00ec1252e7bc441ce` |
| `data/labels/goldset_retest_sept_labeled.csv` |  | `48126e213ecdd1362b4f0309935429f72191791b76bd927c889451008f665736` |
| `data/labels/oracle_labeled_v2.csv` |  | `4f95bff0ded88ad71a05e2463d90f636cc352cd38418a11180d78738ec6ecd95` |
| `data/labels/resolution_annotations.csv` | preliminary annotations (generative assistant, 2026-09-16) for the 38 targets | `99ca582678b8262824cd307ba09812e07dc49d88e8ea57f99d9a219f4383b80f` |
| `data/labels/triage_retest_0818.csv` |  | `6870f78464e4adbf7896bd2910866acf080a87bbfa13a9f6b8308c57bcfdaff8` |
| `data/panel/anchor_gate_full.json` |  | `b4ed7559c98422e16865273ed9f7f1e317514ebc7a1ab7e812a4c3563a3ecce3` |
| `data/panel/calibration_map.csv` |  | `e7e22d948ff35a7d8e3a92610d771e167a65647dc5018dc4cee23c4a633611d6` |
| `data/panel/consistency_input.csv` |  | `6508deb456f16f8af7445773be86dcc75c716eaacb68c0e43bc69c70f30afa14` |
| `data/panel/dsl_results_full.json` |  | `7ed4d66af1a6cc8e72a103245e8f73541b98b5e322d31cb64b7d080913ad7fb5` |
| `data/panel/fulltext/ftcheck_input.csv` |  | `968ea566ee18feb6b0286f15887d23abbd906e66c7d33869258150fe9622e06a` |
| `data/panel/fulltext/ftcheck_raw.jsonl` |  | `748219d12581148ace0305c632e6124cef8574ec5682d31192f3f8b6db1b7991` |
| `data/panel/fulltext/ftcheck_raw_SUPERSEDED_wrongarticle.jsonl` |  | `c469a8c3207f59ce64f708089df5fd98834d0c0f9b13a7f570755d90ec6dd465` |
| `data/panel/fulltext/ftcheck_req.jsonl` |  | `068aa1e206e0b902e4e77940f82a18879fc96cd6fc40c30ee4ce836ee278bf4a` |
| `data/panel/fulltext/ftcheck_result.csv` |  | `bb82ac2b461d590ea95e966dbefd69490277b9e37b3cbb536b016c6a1a843341` |
| `data/panel/fulltext/ftcheck_result_SUPERSEDED_wrongarticle.csv` |  | `cc1067b24b7597f31c684af8d76b76d4630d0c212e3dcfbced22de8ca0455aa3` |
| `data/panel/fulltext/state.json` |  | `9adf04ff220ab6b4c62c752078e0729d8216382bc48c4060a05bd7dd26ade6e6` |
| `data/panel/labels_T1_cons.csv` |  | `5368a3a415c7b9b0e36157dbf81722f633d7951a18adaad67535cdad20de83a5` |
| `data/panel/labels_T1_full.csv` |  | `7016158dea77163c3d53136b46f36c3593f20f2688348cbd8b9f147ff1685ffa` |
| `data/panel/labels_T1_pilot.csv` |  | `84b180ffc1a7228dba1b24d9fa4958d51a7ce41888be5787707f6580c0cc3573` |
| `data/panel/labels_T2_cons.csv` |  | `b4cbe2a894404749812f7e0513c00a93a05205d4fd981b096f2f4544dda76c16` |
| `data/panel/labels_T2_full.csv` |  | `e6e012efae5f9635be5a8b4d4d0ec231c9bcd794df0add635f828be6c1e260a3` |
| `data/panel/labels_T2_pilot.csv` |  | `2cd72fe5dd6032a97010ff054768858ea4f3d68d7bc7527cd8d22ccb4204196d` |
| `data/panel/labels_T3_cons.csv` |  | `89632d22a906ae954468bf5b9d92f85e263c07be6236609a16bbfa16b52a7efb` |
| `data/panel/labels_T3_full.csv` |  | `c3dcb57a4fa8deb9c914ff8fd6981796cad13acfb94b2b34948d4a9efa7a16f6` |
| `data/panel/labels_T3_pilot.csv` |  | `4017dd6f71565c27ac0655224610f0b4500d00e356a1f764eac554ce27b9175a` |
| `data/panel/labels_T4_cons.csv` |  | `c3d547a2a41d1d36e45829542780940d2c8b3407f6646e9ba630066e1c556948` |
| `data/panel/labels_T4_full.csv` |  | `278b623b7719e4e8497841cc223ffcc18597f117a72f0c0be7886ff8a3aeba04` |
| `data/panel/labels_T4_pilot.csv` |  | `09d119b0fa2d13847e6bda1c4f9b3199c1c1f69c390a15e4013833ab6d0f0ccc` |
| `data/panel/labels_T5_cons.csv` |  | `adf930dd0dbca7aba18ee466c624d48b028695ee227fef8dd94f23cc144d9862` |
| `data/panel/labels_T5_full.csv` |  | `3bfa5745892377c130c7c98e499ce39eead1a7c92f8593872070e4d03116d622` |
| `data/panel/labels_T5_pilot.csv` |  | `b3249423a7bd3e9969a5b37f14a83fa7e2ad07723f42f11cd6c5c5de17d51f0d` |
| `data/panel/labels_T6_cons.csv` |  | `1589ba4f08cb2f3cbc0072586e598942a94681827ca64c0a0a8eea9ba5c221d3` |
| `data/panel/labels_T6_full.csv` |  | `0875b541b14b802d1c89d3a8f668e98fce060e7661c21feed36a985018cf8240` |
| `data/panel/labels_T6_pilot.csv` |  | `2d8d1b2244e41ae3c021b49f386939ef9f9ef77a90b9bfeebb81399f5319db89` |
| `data/panel/labels_T7_full.csv` |  | `783b72fec694d3e183d57eff93c5326fc1f584e1a644e6271fc3f5ee492e6a16` |
| `data/panel/labels_T7_pilot.csv` |  | `921552c48fb22e2a40cb7248166378313d663c505513cd5b2bdc076e33b53f6b` |
| `data/panel/manifest.json` |  | `884c4dcca15c074d81b5dd1d4c496c7db0d2ddf01fce70e5c294ec2fe7960736` |
| `data/panel/panel_input.csv` |  | `0d5983015b097cab7d4407a25488ac159b341495979986a3066786d532c8e5d4` |
| `data/panel/state.json` |  | `23ce1977efab2dbc8af961e0895a274116b052e6b91c919194a6e6ff4f13d840` |
| `data/panel/system_prompt.txt` |  | `a61a9c5cb71be4e9e93f9abd52113cf2601e57dce5850c61326aae2e9a197ed5` |
| `data/summary.json` |  | `53d3a79ecd0875e745002782ac9e7ece6dcfa539ad36a8122bcb61804916d1d6` |
| `data/triage_panel/labels_claude-sonnet-5_r1.csv` |  | `30b1e2545bed9a54b5aa7b8f3fd3693e1197496e8c4bfc9d1cde6ffd253e0830` |
| `data/triage_panel/labels_claude-sonnet-5_r2.csv` |  | `925ad47b9b48970030e89bb833448cfdf1321b8582dacb81bc95950b80d99a88` |
| `data/triage_panel/labels_claude-sonnet-5_r3.csv` |  | `e90d6a6f75d499dd754de68396b1e469384254ccbb1673cf80d9d5954d023b13` |
| `data/triage_panel/labels_gpt-5-mini_r1.csv` |  | `60f9f65f3ee5a3a7b13dc3fd9b8ae3420c54384210c7b06b0f78b70904f81e82` |
| `data/triage_panel/labels_gpt-5-mini_r2.csv` |  | `db439cd22d05a92afb5d1b23554e9401308b60ccc8ad4445b1ad7daad5b8c628` |
| `data/triage_panel/labels_gpt-5-mini_r3.csv` |  | `fdfd7e1ee687fda86bc2422dee72da941e5b3fa5bd391a1e97f9a826fa340c5f` |
| `docs/claim_check_result.md` |  | `daca6d2c517135f5652fc7c087aba7b69ffc8d69f58fb191b9f10dec12c4da0f` |
| `docs/deviation_log.md` | deviation log | `524f50de6b045e84fc1b766267e1f95b28ed382c8a8c82a434b120b9293378fa` |
| `docs/sept_retest_result.md` | retest_kappa.py output (2026-10-16 run) | `8ed663f1e14ea9b39164621bbd90009fbe5cca33b75dd9bf6e8951c442f74351` |
| `docs/triage_panel_result.md` |  | `5c8945d44472e17e3b55a91650d8c33f8c4d43932d6c328088f09dcb3714de71` |
| `docs/triage_rubric_T1_v1.md` |  | `48a21c88eefeb7b660f4b38c3842bb589da19c5135dc54494e72d8c7224a3290` |
| `output/figures/fig1_edges.eps` |  | `4d5bdef4ad2b63cf816a5b9fc0cd07e56d5b9c2eac2de9fdcd19500263e14639` |
| `output/figures/fig1_edges.pdf` |  | `415fedb4a9ad555512f56edf1b4c1804a92f3217c5d68e11a621d446d50043a9` |
| `output/figures/fig1_edges.png` |  | `0760fa288789cd51c3ecbba47b26b631c4433a56381e906b01e83ae46a36f399` |
| `output/figures/fig2_triage.eps` |  | `3023a474d3a0b70412a225494142e34d72e9262f5ceb41f92196292543ba0866` |
| `output/figures/fig2_triage.pdf` |  | `46457e0ba34f53343d8a082106fadcbdb608bfa43bc109a5206c467c4b48d133` |
| `output/figures/fig2_triage.png` |  | `973eebc174ce659de0322bfd860f443feb143188ddcc82784dc1de3b4544c9e5` |
| `output/tables/clause_reading_C01_C20.csv` |  | `b6403fb037e78d6c1b63fb9fa4328d9c64b23f1d38a051dbe0f0cf2d45c164a9` |
| `output/tables/resolution/d1_matching_sensitivity.csv` | D1 under identifier-only vs identifier-or-title matching (2026-10-16) | `5ce36108d9268d30785f45c24873e732750df5e52befb6b8d7e0d1533d5921a0` |
| `output/tables/resolution/resolution_stages.csv` |  | `b962c59c4da042e8d2668117d86050b8cb36e82df5f9d16f5dad9b58c3b2f683` |
| `output/tables/resolution/resolution_table.csv` | 38 unresolved targets, auto + preliminary annotations merged | `41e285f32d840b47d6540d2bcd633c1e48b279a145bc739020853a0060ced0ee` |
| `output/tables/resolution/resolution_table_auto.csv` | 38 unresolved targets, script candidate causes | `5a263ddb74dd18ade50a0889db168d1e0f573c55edec7656a87bb5af9b34d69b` |
| `output/tables/resolution/rule_resolution_audit.csv` | 280 rule-directed links, all title candidates (2026-10-16) | `3c1fa38c1b85866732550fd77810740e901f86c743c084fbfd14ec67451a808f` |
| `output/tables/table6_agreement.csv` | agreement table (current, 2026-10-16) | `9411671e892cc91e6e9a9f8435210fccfeb6e9eeea672385fa7ac80e6ebbe7e1` |
| `output/tables/table7_audit_SUPERSEDED_2026-08.csv` | August summary, superseded; historical artefact | `83f66da60f6d2e16de92e5604bf73a39d2d9fbd918f049f69e93b30503a262ac` |
| `output/tables/weighted/sentence_group_sensitivity.csv` |  | `7ca4b14973b9daa1b2eb43278f03d411209afc35cf727ebcc5e362b204780490` |
| `output/tables/weighted/shared_error_sensitivity.csv` |  | `afc69075a66b09d93f8dfb53452719d73a43076f73748b974139e1207828ef6e` |
| `output/tables/weighted/strata_table.csv` | Table S3.3 | `bdb738fbc9004d900367c6e6f845c09d8c2cd2aa9a776491be44781fd1437752` |
| `output/tables/weighted/task_a_summary.json` |  | `26f63ea267da8b8335e99e44fa12b4326eea073ce917ac75d785ef00b85082a5` |
| `output/tables/weighted/tipping_weighted.csv` |  | `9ffc19279d6d519dd46ae0a283f125fd8799ee1680e7387529298217c8c8c80a` |
| `output/tables/weighted/weighted_estimates.csv` | Table S3.2 estimates | `5e29f0c2f67e0459aa341c9fc776e8d32facc831b7a02d577077c47f1693332f` |
| `requirements-repro.txt` | pinned environment of the reproduction run | `a1b8e0ea1c4b88af7dd8fbe44b442f2f0dcb6d1c18815927d84026bb6b37df53` |
| `requirements.txt` |  | `209e1da5d2db63b9cfab55375c11fa874941bcf6ab06fb035f9d72d89f14be4f` |
| `scripts/reproduce.py` | one-command reproduction | `61981adb09ed988b4c6997230643651ecb96fd335b1725a7e64d12392cad911a` |
| `scripts/run_crossref.sh` |  | `7b8fac0c5668c52772b44561020d2ee9496c007415467d38ac28127d17ec6665` |
| `scripts/run_llm.sh` |  | `0c1d8c144335ae0bf598dc263edaf64536d25e4229b1abf2bf9fcc71a2216157` |
| `scripts/run_oracle.sh` |  | `0bb68c3c3449bde6811db4d416de4396e5c8dc408d0bd183da179af0ed8f7c49` |
| `scripts/run_oracle_detc.sh` |  | `98cebf642e652dac9c9535bc5c9b99a54eb851f513d298c5b2cbcd23920f0779` |
| `scripts/run_pipeline.sh` |  | `a8d3861a6b7440f9990793ceb119bde606370c44bdaedfe61ad90178749ef47e` |
| `sim/c1_directional_sim.py` |  | `71ad3686ccec32a68d59829e9913877f427bd295ae2ac5f1366f5a837b237594` |
| `sim/dsl_counter_sim.py` |  | `6363f27d049a4f7269ed212b79c178102d2a0a4cba85d429d98575c0cc34b91b` |
| `sim/lcm_sim.py` |  | `ee430dfd94ab3bfd7db4524873a0101a41dc747d74a9892dfa71db4a04abc526` |
| `sim/lcm_sim2.py` |  | `666568b5617ab92ade1dbd20d5f5874bbce63409dcba841350ee95c22fcc6d34` |
| `src/agreement.py` |  | `29d36cc6ee158eb406cd2ab9a15cd1b1e39265d389f091bc28c969edd85bfc1a` |
| `src/anchors.py` |  | `bfd0683f171d9e0de555fa6e9e5842855c7acfcbee1bf5619e5d95c7737a4b67` |
| `src/claim_check.py` |  | `64a6799889db869bc957c8faabb79f018bbd1329c506ff30d722670610cf50d8` |
| `src/collect_moleg.py` |  | `63370c1ce1b6e37add681287cc4405d4e0bb2e9b8a55655563ea5411437f91f5` |
| `src/dsl_estimate.py` | registered estimator | `53b96a5bcee43a06a21bfa8a8d0e42dcde5fee81e30adf012409f7efc33f7b3f` |
| `src/dsl_weighted.py` | design-weighted re-analysis | `566cf87391f95a52ac9294d5b4a08599f0e0aae59a408282c17edc720cf08eb3` |
| `src/fulltext_check.py` |  | `fb19f60fc99faae32fd3ffaa09001d613bfcd0eb6de6ba3b5e9bddeb8c541c02` |
| `src/l2_agreement.py` | L2 agreement figures of Table 2 / S1.1 (2026-10-16) | `341b336d904750436cd0f2799fb6b05fd02f0398b668195721933e01bc78239b` |
| `src/llm_annotate.py` |  | `0b6768a1b514f44b484c9a6167faa51a045b3f3582b955111bd59a5de1dfae25` |
| `src/make_deposit.py` |  | `b27492cc6f672445a34c77d0b1e1f44f580ac352a043bac52b60ef992611506c` |
| `src/make_figures.py` |  | `5096c9e78b9eec8d7ffe769d900f4077ad2635354ddfc56081adc4ad77f6a6bc` |
| `src/make_public.py` |  | `49989c1d3af58958a355c522f3f81307447accd869aca53bee8234a8dfa2dc3c` |
| `src/make_retest_workbook.py` |  | `7e26b5f3375ce2fd640deeeea46bd33a6f124ba3e6c6e19c3515968eb6f295a0` |
| `src/panel_annotate.py` |  | `70bc4afcce81fe5aab8281c7014ffbc16ce42497ec530cb6815ad49aa59a0cbb` |
| `src/resolve_external_claims.py` |  | `6bdb9ee831052502c56bcb031d9c208248f6980c91ad877fd7c7cf34b98d1c5f` |
| `src/resolve_rule_ids.py` |  | `026465d1a65e0e0020b637b1224879554c52aad87d67eeded9fca016d90ed64d` |
| `src/retest_kappa.py` |  | `549d1be45337332e0c7978999e8ebb5bea7270477591a072deac8b09fefb2a5e` |
| `src/triage_panel.py` |  | `b6fa08dabf59b365970031863b5ec8561fd6dfd1f6321fa67a9754935bc95084` |
