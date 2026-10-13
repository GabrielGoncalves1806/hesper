# Room acoustic measurement, decay analysis and simulation data — St. Nicholas Chapel, Aachen Cathedral
Version 1.2 (2026-10-12)

This dataset contains the measured room impulse responses, the room-acoustic
parameters and decay analyses derived from them, and the results of a
geometrical-acoustics (ODEON) and a hybrid wave-based/geometrical (TREBLE)
simulation of the St. Nicholas Chapel (Nikolauskapelle), a late-Gothic two-storey
hall chapel of Aachen Cathedral (volume ≈ 3050 m³, mid-frequency reverberation time
≈ 4.6 s). It accompanies the journal article by M. Zerwas and S. Kayku (Acta Acustica,
forthcoming) and extends the preliminary report presented at DAGA 2026
(https://doi.org/10.71568/DAGA2026.137).

All CSV files are semicolon-separated, use a decimal comma and are UTF-8 encoded.
Source positions: S1 (main hall), S2 (polygonal apse on the ground floor, aligned
with the altar wall), S3 (gallery level, above S2). Receivers R1–R22 on the ground
floor: R1–R13 in the main hall, R14–R22 in the ambulatory and aisles.

## Measurement data

- **impulse_responses.zip** — 46 measured room impulse responses (4-channel B-format,
  FuMa convention, 48 kHz, WAV), omnidirectional dodecahedron source (NTi DS3 + PA3,
  Mackie Thump 118s subwoofer, crossover 100 Hz) and Sennheiser AMBEO VR microphone
  with IRIS 3D, exponential sine sweep (20 s, one sweep per response), following
  ISO 3382-1. Three subfolders by source position:
    - `Nikolauskapelle_Source1_BRIR/` — 22 files (S1; receivers R1–R22 without R5,
      plus R23, a position without a counterpart in the receiver grid that is not
      part of the 45 combinations evaluated in the article)
    - `Nikolauskapelle_Source2_BRIR/` — 12 files (S2; receivers R1–R12)
    - `Nikolauskapelle_Source3_BRIR/` — 12 files (S3; receivers R1–R12)
  File naming: `S<source>-Do_R<receiver>.wav` ("Do" = dodecahedron).
  B-format channel order: W, X, Y, Z (W scaled by 1/√2). The microphone stood
  upright; its front axis followed the orientation shown in the receiver plan of the
  article (Fig. 4a).

- **Nikolauskapelle_Source{1,2,3}_Results_20260205.xlsx** — room-acoustic parameters
  derived with IRIS 3D (one file per source position). Sheet `Parameters`: 19 ISO 3382-1
  parameters per receiver in 29 one-third-octave bands (25 Hz – 16 kHz); omnidirectional
  parameters from the W channel, LF and LFC from the W and Y channels; integration
  limits and background-noise compensation as implemented in IRIS. Sheet `Speech`:
  STI, STIPA, speech level, U50, U80 in 7 octave bands; STI was computed without a
  background-noise level. Octave values in the article are means of the three
  one-third-octave bands per octave. Air temperature and relative humidity during the
  campaign: 14 ± 1 °C and 60 ± 5 %.

- **positions.csv** — coordinates of the three sources and 22 receivers in the frame
  of the simulation model (x, y horizontal, z vertical, z = 0 on the ground floor), in
  metres, with the height above the respective floor and the region.
  Columns: `type, id, x_m, y_m, z_m, height_above_floor_m, region`.

- **source_receiver_distances.csv** — source–receiver distances of the 45 evaluated
  combinations: as detected by IRIS from the direct-sound arrival, as computed from the
  model geometry, and as used in the analyses. At S3 the direct sound is partly screened
  by the gallery balustrade; the IRIS detection overestimates the distance there by
  3.1 m on average (up to 8.5 m), and the geometric distance is used. At S1 and S2 the
  two agree to within 0.1 m on average, and the IRIS distance is used.
  Columns: `source, receiver, distance_iris_m, distance_geometric_m, distance_used_m`.

## Decay and direction analyses of the measurements

- **decayfitnet_all_positions.csv** — two-component decay analysis of the 45
  combinations in the octave bands 63, 125, 250 and 500 Hz with DecayFitNet
  (Götz et al., 2022; model order fixed at two, seed 42). The decay curve starts at the
  direct-sound arrival given by `distance_m`.
  Columns: `source, receiver, position, distance_m, ir_length_s, truncated_length_s,
  band_hz, T1_s, T2_s, A1, A2, A1_pct, A2_pct, noise_floor`
  (T1/T2 = 60 dB decay times in seconds; A1/A2 = amplitudes relative to the decay
  curve normalised to 0 dB; A1_pct/A2_pct = normalised amplitude shares; noise_floor =
  fitted noise level per original sample).

- **bayesian_all_positions.csv** — Bayesian model-order selection (one, two or three
  components; Xiang et al.) for the same 180 band–position combinations, slice
  sampling with three random seeds and 2000 iterations per model order; parameter grids
  of 100 points, decay times 0.5–12 s, amplitudes 10⁻³ to 10^0.5 relative to the
  normalised decay curve, noise 10⁻¹⁰ to 10⁻². The upper amplitude bound exceeds the
  toolbox default of 10⁰, because at the gallery source the decay starts more slowly
  than it continues (EDT > T30) and the default bound biases the selection towards two
  near-identical components.
  Columns: `source, receiver, position, distance_m, band_hz, n_slopes_majority,
  orders_all_seeds, order_stable, dbic_2_1_median, dbic_2_1_min, dbic_2_1_max,
  two_beats_one_frac, T1_s, A1_pct, T2_s, A2_pct, T3_s, A3_pct`
  (n_slopes_majority = order selected by majority over the seeds; orders_all_seeds =
  per-seed orders; order_stable = 1 if all seeds agree; dbic_2_1_* = BIC difference
  between the two- and the one-component model over the seeds, positive values favour
  two components; two_beats_one_frac = share of seeds preferring two components;
  T*/A* = decay times and amplitude shares of the run whose order equals the majority
  and whose ΔBIC is closest to the median).

- **directional_multi_positions.csv** — energy-weighted mean azimuth and elevation of
  arrival in an early (15–55 ms after the direct sound) and a late (125–375 ms) window
  at seven combinations, from the active intensity of the B-format responses, with 95 %
  block-bootstrap intervals (block length 1/B). The article tests the elevation shift
  only at 250 and 500 Hz; at 63 Hz the early window contains one independent block
  (no interval) and at 125 Hz three (indicative intervals only).
  Columns: `source, receiver, position, note, distance_m, t_direct_ms, band_hz,
  R_early, az_early_deg, az_early_ci95, n_blocks_early, R_late, az_late_deg,
  az_late_ci95, n_blocks_late, drift_deg, drift_margin_deg, drift_resolved,
  el_early_deg, el_early_ci95, el_late_deg, el_late_ci95, d_elevation_deg,
  d_elevation_ci95, el_resolved, el_disjoint`
  (note = why the position was selected; R = circular concentration of the azimuth;
  drift_* = azimuthal drift between the windows; d_elevation_deg = late minus early
  elevation; d_elevation_ci95 = 95 % bootstrap interval of this difference, the two
  windows resampled independently; el_resolved = 1 if that interval excludes zero;
  el_disjoint = 1 if the two window intervals do not overlap).

## Simulation data

Both models use the same plane-polygon model (1830 surfaces) derived from a
third-party laser scan (not redistributed) and the same absorption and scattering
coefficients, calibrated in ODEON with the Genetic Material Optimizer against EDT and
T30 (125–4000 Hz) at seven combinations (R1, R13, R16, R19, R22 at S1; R1 at S2 and
S3) at 14 °C / 60 %. Sources are omnidirectional point sources 1.50 m above the
respective floor, receivers omnidirectional points at the measured positions.
ODEON V18: impulse-response length 7 s, 2452 late rays, transition order 2,
reflection-based scattering. TREBLE: discontinuous-Galerkin wave solver up to 177 Hz,
geometrical solver above (80,000 rays, image-source order 3), impulse-response length
7 s; runs of 10 October 2026 (unoccupied) and 11 October 2026 (occupied). In the
occupied runs the audience material replaces the pew material; all other data and
settings are unchanged.

- **materials.csv** — material groups with their areas in the ODEON model (stone
  including the floor; for the pews the exposed area, whereas the ODEON layer of
  81.8 m² also contains the concealed underside of the pew blocks), initial
  values (where taken from the literature) and calibrated absorption coefficients per
  octave band (63 Hz – 8 kHz), scattering coefficient, and the audience material of the
  occupied runs. The 63 Hz and 8 kHz values were not constrained by the calibration.
  The TREBLE model carries the same coefficients; its layer areas differ slightly, and
  its impedance fit reproduces the coefficients to within 0.013 (stone) to 0.063
  (small groups).

- **simulation_parameters.csv** — room-acoustic parameters of all 66 source–receiver
  combinations (S1–S3 × R1–R22) in the octave bands 63 Hz – 8 kHz for five runs:
  ODEON unoccupied at 14 °C / 60 % and at 20 °C / 50 %, ODEON occupied at
  14 °C / 60 %, TREBLE unoccupied and occupied. TREBLE computes at approximately
  20 °C (documented speed of sound 343 m/s, air density 1.2 kg/m³) with an undocumented
  humidity, taken as 50 %; its reverberation times converted to 14 °C / 60 % with the
  Sabine relation including air attenuation after ISO 9613-1 (Equation (4) of the
  article) are given in the columns `*_at_14C60`.
  Columns: `model, state, air_conditions, source, receiver, band_hz,
  measured_combination, EDT_s, T20_s, T30_s, C50_dB, C80_dB, D50, Ts_ms, G_dB, LF, LFC,
  EDT_s_at_14C60, T20_s_at_14C60, T30_s_at_14C60`
  (measured_combination = 1 for the 45 combinations of the measurement grid; LFC is not
  provided by TREBLE).

- **decayfitnet_simulations.csv** — the same DecayFitNet analysis as for the
  measurement, applied to the simulated impulse responses of the 45 measured
  combinations for both models and both occupancy states.
  Columns: `model, state, source, receiver, position, is_calibration_position,
  distance_m, ir_length_s, band_hz, T1_s, T2_s, A1, A2, A1_pct, A2_pct,
  T2_extrapolated, noise_floor, source_file`.

- **simulated_impulse_responses.zip** — simulated impulse responses as exported by
  the programs, in the subfolders `unoccupied/` and `occupied/`:
  `Odeon_S<k>R<n>_mono.wav` / `OdeonOcc_S<k>R<n>_mono.wav` (two channels, 44.1 kHz,
  16 bit; the analyses use the mean of both channels) and
  `Treble_S<k>R<n>_hybrid_IR.wav` / `TrebleOcc_S<k>R<n>_hybrid_IR.wav` (one channel,
  32 kHz, 32-bit float). The ODEON responses end where the decay has fallen by 60 to
  70 dB below its maximum.

## Changes in version 1.2

- Revised analyses replace the files of version 1.1: source–receiver distances at S3
  from the model geometry (decay analysis), Bayesian model selection with the extended
  amplitude bound, and the direction-resolved table with the bootstrap interval of the
  elevation difference.
- New: positions, distances, material set, simulation results of both models in the
  unoccupied and occupied state, decay analysis of the simulated responses, simulated
  impulse responses.
- README: description of R23 corrected (not a repeat measurement), S2 described as
  apse source, measurement chain and simulation settings documented.

## Not included in this deposit

The background-noise measurement, the analysis code and the compiled object list of
the comparison corpus are available from the corresponding author on reasonable
request. The 3D geometry is derived from a third-party laser scan of Aachen Cathedral
and is not redistributed here (available from the laser-scan authors under their
data-sharing agreement). The church reverberation-time data of Data Set Peutz are
third-party data (Peutz Consult GmbH, personal communication).

## License and citation

Data: Creative Commons Attribution 4.0 International (CC-BY-4.0).
© 2026 Martin Zerwas and Selin Kayku.
When using these data, please cite the associated article (M. Zerwas and S. Kayku,
Acta Acustica, forthcoming) and this dataset (DOI 10.5281/zenodo.20428704).

## Contact

Martin Zerwas, FH Aachen University of Applied Sciences, Faculty of Architecture,
52066 Aachen, Germany — zerwas@fh-aachen.de
