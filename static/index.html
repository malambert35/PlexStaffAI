<!DOCTYPE html>
<html>
<head>
    <title>PlexStaffAI Dashboard</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white p-8">
    <div class="max-w-4xl mx-auto">
        <h1 class="text-4xl font-bold mb-8 text-blue-400">🚀 PlexStaffAI Admin</h1>
        
        <!-- Stats -->
        <div class="grid grid-cols-3 gap-4 mb-8" id="stats">
            <div class="bg-gray-800 p-6 rounded-lg">
                <h3>Total Décisions</h3>
                <div id="total" class="text-3xl font-bold text-green-400">--</div>
            </div>
            <div class="bg-gray-800 p-6 rounded-lg">
                <h3>Dernier Run</h3>
                <div id="last-run" class="text-xl">--</div>
            </div>
            <div class="bg-gray-800 p-6 rounded-lg">
                <h3>Status Cron</h3>
                <div id="cron-status" class="text-xl">--</div>
            </div>
        </div>

        <!-- Actions -->
        <div class="flex gap-4 mb-8">
            <button hx-get="/staff/moderate" 
                    hx-target="#results" 
                    hx-swap="innerHTML"
                    class="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-bold">
                🔄 Modérer Requests
            </button>
            <button hx-get="/staff/report" 
                    hx-target="#report"
                    class="bg-green-600 hover:bg-green-700 px-6 py-3 rounded-lg font-bold">
                📊
                Rapport IA
            </button>
        </div>

        <!-- Results -->
        <div id="results" class="bg-gray-800 p-6 rounded-lg mb-4">
            <h3>Résultats Récents</h3>
            <div>Click Modérer pour commencer...</div>
        </div>

        <!-- Report -->
        <div id="report" class="bg-indigo-900 p-6 rounded-lg">
            <h3>Insights IA</h3>
            <div>Click Rapport...</div>
        </div>
    </div>

    <script>
        // Auto-refresh stats
        setInterval(() => {
            htmx.ajax('GET', '/staff/report', {
                target: '#stats', swap: 'innerHTML'
            })
        }, 30000);
    </script>
</body>
</html>
