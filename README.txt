QuantIQ backend fixes

Replace the existing backend files with:
- planner.py
- main.py
- sql_builder.py

What this fixes:
1. "Which car has the highest selling price?" is treated as a ranking/record question instead of returning only MAX(price).
2. "Top 5 records by price" returns the actual records in the answer.
3. The answer formatter no longer says only "I found 5 matching records".
4. The planner remains dataset-independent and uses the uploaded schema.

After replacing the files:
1. Stop the FastAPI server with Ctrl+C.
2. Start it again using your normal command.
3. Keep Ollama running with the CPU library setting that worked for you:
   $env:OLLAMA_LLM_LIBRARY="cpu_avx2"
4. Upload the dataset again if necessary.
