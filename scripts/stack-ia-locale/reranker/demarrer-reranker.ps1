# demarrer-reranker.ps1 : reranker bge-reranker-v2-m3 sur la carte du serveur de modèles
# (llama-server --reranking, §10.8, 2.23.0). Lancé par la tâche planifiée
# « Reranker llama-server (lab) » à l'ouverture de session, comme Ollama.
#
# La clé d'API est lue dans un fichier lisible par le seul compte qui lance le
# service, et passée par la variable LLAMA_API_KEY : elle n'apparaît pas dans la
# ligne de commande du processus, visible par tout administrateur du poste.
# --cache-ram 0 : pas de cache de prompts en mémoire centrale (8 Gio par défaut).
#
# llama-server écrit son journal sur la sortie d'erreur : Windows PowerShell 5.1
# transforme chaque ligne en erreur si on la redirige avec 2> ou *>, ce qui
# arrêtait le script. Start-Process écrit les deux sorties dans des fichiers,
# remplacés à chaque démarrage.

$env:LLAMA_API_KEY = (Get-Content 'C:\IA\reranker\cle.txt' -Raw).Trim()
Start-Process -FilePath 'C:\IA\llama.cpp\llama-server.exe' -WindowStyle Hidden -Wait `
    -RedirectStandardError 'C:\IA\reranker\reranker.log' `
    -RedirectStandardOutput 'C:\IA\reranker\reranker-sortie.log' `
    -ArgumentList '-m C:\IA\reranker\bge-reranker-v2-m3-q8_0.gguf --reranking --host 0.0.0.0 --port 8091 -ngl 99 -c 8192 -np 4 -b 2048 -ub 2048 --cache-ram 0'
