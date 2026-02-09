// Traductions FR/EN - Version complète
const translations = {
    fr: {
        // ===== INDEX.HTML =====
        title: "PlexStaffAI Admin",
        subtitle: "IA Moderation Overseerr • Auto-Scan",
        version: "Smart Rules + ML Learning",
        autoScanActive: "Auto-Scan Actif • Toutes les",
        systemLive: "Système Live • Cron Actif",
        reviewDashboard: "Tableau de Révision",
        managePending: "Gérer les révisions en attente",
        pendingReviews: "En attente",
        reviews: "Révisions",
        moderateNow: "MODÉRER MAINTENANT",
        refreshStats: "ACTUALISER STATS",
        viewHistory: "VOIR HISTORIQUE",
        totalDecisions: "Total",
        totalDecisionsDesc: "Décisions totales",
        approved: "Approuvés",
        approvedDesc: "Requests validées",
        rejected: "Rejetés",
        rejectedDesc: "Requests refusées",
        approvalRate: "Taux",
        approvalRateDesc: "Taux d'approbation",
        resultsTitle: "Résultats Modération IA",
        resultsDesc: "Clique",
        resultsDesc2: "pour scanner immédiatement",
        autoScanInfo: "Le système scanne automatiquement toutes les",
        loading: "⏳ Modération en cours...",
        quickLinks: "Liens Rapides",
        apiDocs: "Documentation API",
        healthCheck: "État Système",
        fullReport: "Rapport Complet",
        openaiStats: "Statistiques OpenAI",
        poweredBy: "Propulsé par",
        dockerHub: "Docker Hub",
        minute: "minute",
        minutes: "minutes",
        
        // ===== HEALTH PAGE =====
        healthTitle: "État du Système",
        healthStatus: "Statut",
        healthOk: "Opérationnel",
        healthVersion: "Version",
        healthUptime: "Temps de fonctionnement",
        healthDatabase: "Base de données",
        healthConnected: "Connectée",
        healthOpenAI: "OpenAI API",
        healthConfigured: "Configurée",
        healthOverseerr: "Overseerr",
        healthTMDB: "TMDB API",
        healthBackToDashboard: "Retour au Dashboard",
        
        // ===== HISTORY PAGE =====
        historyTitle: "Historique des Décisions",
        historyRequestId: "ID Request",
        historyMedia: "Média",
        historyUser: "Utilisateur",
        historyDecision: "Décision",
        historyReason: "Raison",
        historyConfidence: "Confiance",
        historyDate: "Date",
        historyNoDecisions: "Aucune décision enregistrée",
        historyLoadMore: "Charger plus",
        historyFilterAll: "Toutes",
        historyFilterApproved: "Approuvées",
        historyFilterRejected: "Rejetées",
        historyFilterReview: "En révision",
        historyExportCSV: "Exporter CSV",
        
        // ===== REVIEW DASHBOARD =====
        reviewTitle: "Tableau de Révision",
        reviewPending: "Révisions en Attente",
        reviewNoPending: "Aucune révision en attente",
        reviewMediaTitle: "Titre",
        reviewRequestedBy: "Demandé par",
        reviewAIDecision: "Décision IA",
        reviewAIReason: "Raison IA",
        reviewAIConfidence: "Confiance",
        reviewActions: "Actions",
        reviewApprove: "Approuver",
        reviewReject: "Rejeter",
        reviewViewDetails: "Voir détails",
        reviewProcessing: "Traitement en cours...",
        reviewSuccess: "✅ Décision appliquée",
        reviewError: "❌ Erreur lors du traitement",
        
        // ===== REPORT PAGE =====
        reportTitle: "Rapport Complet",
        reportOverview: "Vue d'ensemble",
        reportTotalRequests: "Total des requests",
        reportApprovalRate: "Taux d'approbation",
        reportAverageConfidence: "Confiance moyenne",
        reportMostActive: "Utilisateur le plus actif",
        reportByDecision: "Par décision",
        reportByUser: "Par utilisateur",
        reportByMediaType: "Par type de média",
        reportRecentActivity: "Activité récente",
        reportMovies: "Films",
        reportSeries: "Séries",
        reportExport: "Exporter",
        reportRefresh: "Actualiser",
        
        // Common
        backToDashboard: "← Retour au Dashboard",
        loading: "Chargement...",
        error: "Erreur",
        success: "Succès",
        close: "Fermer",
        save: "Enregistrer",
        cancel: "Annuler",
        delete: "Supprimer",
        edit: "Modifier",
        view: "Voir"
    },
    en: {
        // ===== INDEX.HTML =====
        title: "PlexStaffAI Admin",
        subtitle: "AI Moderation Overseerr • Auto-Scan",
        version: "Smart Rules + ML Learning",
        autoScanActive: "Auto-Scan Active • Every",
        systemLive: "System Live • Cron Active",
        reviewDashboard: "Review Dashboard",
        managePending: "Manage pending reviews",
        pendingReviews: "Pending",
        reviews: "Reviews",
        moderateNow: "MODERATE NOW",
        refreshStats: "REFRESH STATS",
        viewHistory: "VIEW HISTORY",
        totalDecisions: "Total",
        totalDecisionsDesc: "Total decisions",
        approved: "Approved",
        approvedDesc: "Validated requests",
        rejected: "Rejected",
        rejectedDesc: "Declined requests",
        approvalRate: "Rate",
        approvalRateDesc: "Approval rate",
        resultsTitle: "AI Moderation Results",
        resultsDesc: "Click",
        resultsDesc2: "to scan immediately",
        autoScanInfo: "System automatically scans every",
        loading: "⏳ Moderation in progress...",
        quickLinks: "Quick Links",
        apiDocs: "API Docs",
        healthCheck: "Health Check",
        fullReport: "Full Report",
        openaiStats: "OpenAI Stats",
        poweredBy: "Powered by",
        dockerHub: "Docker Hub",
        minute: "minute",
        minutes: "minutes",
        
        // ===== HEALTH PAGE =====
        healthTitle: "System Health",
        healthStatus: "Status",
        healthOk: "Operational",
        healthVersion: "Version",
        healthUptime: "Uptime",
        healthDatabase: "Database",
        healthConnected: "Connected",
        healthOpenAI: "OpenAI API",
        healthConfigured: "Configured",
        healthOverseerr: "Overseerr",
        healthTMDB: "TMDB API",
        healthBackToDashboard: "Back to Dashboard",
        
        // ===== HISTORY PAGE =====
        historyTitle: "Decision History",
        historyRequestId: "Request ID",
        historyMedia: "Media",
        historyUser: "User",
        historyDecision: "Decision",
        historyReason: "Reason",
        historyConfidence: "Confidence",
        historyDate: "Date",
        historyNoDecisions: "No decisions recorded",
        historyLoadMore: "Load more",
        historyFilterAll: "All",
        historyFilterApproved: "Approved",
        historyFilterRejected: "Rejected",
        historyFilterReview: "Under Review",
        historyExportCSV: "Export CSV",
        
        // ===== REVIEW DASHBOARD =====
        reviewTitle: "Review Dashboard",
        reviewPending: "Pending Reviews",
        reviewNoPending: "No pending reviews",
        reviewMediaTitle: "Title",
        reviewRequestedBy: "Requested by",
        reviewAIDecision: "AI Decision",
        reviewAIReason: "AI Reason",
        reviewAIConfidence: "Confidence",
        reviewActions: "Actions",
        reviewApprove: "Approve",
        reviewReject: "Reject",
        reviewViewDetails: "View details",
        reviewProcessing: "Processing...",
        reviewSuccess: "✅ Decision applied",
        reviewError: "❌ Error processing",
        
        // ===== REPORT PAGE =====
        reportTitle: "Full Report",
        reportOverview: "Overview",
        reportTotalRequests: "Total requests",
        reportApprovalRate: "Approval rate",
        reportAverageConfidence: "Average confidence",
        reportMostActive: "Most active user",
        reportByDecision: "By decision",
        reportByUser: "By user",
        reportByMediaType: "By media type",
        reportRecentActivity: "Recent activity",
        reportMovies: "Movies",
        reportSeries: "Series",
        reportExport: "Export",
        reportRefresh: "Refresh",
        
        // Common
        backToDashboard: "← Back to Dashboard",
        loading: "Loading...",
        error: "Error",
        success: "Success",
        close: "Close",
        save: "Save",
        cancel: "Cancel",
        delete: "Delete",
        edit: "Edit",
        view: "View"
    }
};

function t(key) {
    const lang = localStorage.getItem('language') || 'fr';
    return translations[lang][key] || key;
}

function setLanguage(lang) {
    localStorage.setItem('language', lang);
    updatePageLanguage();
}

function updatePageLanguage() {
    const lang = localStorage.getItem('language') || 'fr';
    
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        const translation = t(key);
        if (translation) {
            element.textContent = translation;
        }
    });
    
    document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
        const key = element.getAttribute('data-i18n-placeholder');
        element.placeholder = t(key);
    });
    
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    const activeBtn = document.querySelector('[data-lang="' + lang + '"]');
    if (activeBtn) {
        activeBtn.classList.add('active');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    updatePageLanguage();
});
