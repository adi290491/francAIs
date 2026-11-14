"""A transcription response shaped like the one DeepInfra returned in the step 0 check.

Hesitant French with fillers and three inserted silences (0.90 s, 1.32 s, 0.69 s). Note the
split fragment `" s"` + `"'il"`, which the transcriber must join into one word.
"""

HESITANT_TEXT = "Euh, alors… je, je voudrais… hum. Un café, s'il vous plaît, euh."

HESITANT_RESPONSE = {
    "text": " " + HESITANT_TEXT,
    "language": "french",
    "duration": 10.3,
    "words": [
        {"word": " Euh,", "start": 0.00, "end": 0.40},
        {"word": " alors…", "start": 0.50, "end": 1.10},
        {"word": " je,", "start": 2.00, "end": 2.20},
        {"word": " je", "start": 2.30, "end": 2.45},
        {"word": " voudrais…", "start": 2.50, "end": 3.10},
        {"word": " hum.", "start": 3.20, "end": 3.60},
        {"word": " Un", "start": 4.92, "end": 5.05},
        {"word": " café,", "start": 5.10, "end": 5.60},
        {"word": " s", "start": 5.70, "end": 5.75},
        {"word": "'il", "start": 5.75, "end": 5.90},
        {"word": " vous", "start": 5.95, "end": 6.10},
        {"word": " plaît,", "start": 6.15, "end": 6.70},
        {"word": " euh.", "start": 7.39, "end": 7.80},
    ],
}
