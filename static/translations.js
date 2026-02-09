// Traductions FR/EN
const translations = {
    fr: {
        // Header
        title: "PlexStaffAI Admin",
        subtitle: "IA Moderation Overseerr • Auto-Scan",
        version: "Smart Rules + ML Learning",
        
        // Auto-scan badge
        autoScanActive: "Auto-Scan Actif • Toutes les",
        systemLive: "Système Live • Cron Actif",
        
        // Review Dashboard button
        reviewDashboard: "Review Dashboard",
        managePending: "Manage pending reviews",
        pendingReviews: "Pending",
        reviews: "Reviews",
        
        // Buttons
        moderateNow: "MODÉRER MAINTENANT",
        refreshStats: "REFRESH STATS",
        viewHistory: "VOIR HISTORIQUE",
        
        // Stats cards
        totalDecisions: "Total",
        totalDecisionsDesc: "Décisions totales",
        approved: "Approuvés",
        approvedDesc: "Requests validées",
        rejected: "Rejetés",
        rejectedDesc: "Requests refusées",
        approvalRate: "Taux",
        approvalRateDesc: "Taux d'approbation",
        
        // Results panel
        resultsTitle: "Résultats Modération IA",
        resultsDesc: "Clique",
        resultsDesc2: "pour scanner immédiatement",
        autoScanInfo: "Le système scanne automatiquement toutes les",
        
        // Loading
        loading: "Modération en cours...",
        
        // Quick links
        quickLinks: "Quick Links",
        apiDocs: "API Docs",
        healthCheck: "Health Check",
        fullReport: "Rapport Complet",
        openaiStats: "OpenAI Stats",
        
        // Footer
        poweredBy: "Powered by",
        dockerHub: "Docker Hub",
        
        // Misc
        minute: "minute",
        minutes: "minutes"
    },
    en: {
        // Header
        title: "PlexStaffAI Admin",
        subtitle: "AI Moderation Overseerr • Auto-Scan",
        version: "Smart Rules + ML Learning",
        
        // Auto-scan badge
        autoScanActive: "Auto-Scan Active • Every",
        systemLive: "System Live • Cron Active",
        
        // Review Dashboard button
        reviewDashboard: "Review Dashboard",
        managePending: "Manage pending reviews",
        pendingReviews: "Pending",
        reviews: "Reviews",
        
        // Buttons
        moderateNow: "MODERATE NOW",
        refreshStats: "REFRESH STATS",
        viewHistory: "VIEW HISTORY",
        
        // Stats cards
        totalDecisions: "Total",
        totalDecisionsDesc: "Total decisions",
        approved: "Approved",
        approvedDesc: "Validated requests",
        rejected: "Rejected",
        rejectedDesc: "Declined requests",
        approvalRate: "Rate",
        approvalRateDesc: "Approval rate",
        
        // Results panel
        resultsTitle: "AI Moderation Results",
        resultsDesc: "Click",
        resultsDesc2: "to scan immediately",
        autoScanInfo: "System automatically scans every",
        
        // Loading
        loading: "Moderation in progress...",
        
        // Quick links
        quickLinks: "Quick Links",
        apiDocs: "API Docs",
        healthCheck: "Health Check",
        fullReport: "Full Report",
        openaiStats: "OpenAI Stats",
        
        // Footer
        poweredBy: "Powered by",
        dockerHub: "Docker Hub",
        
        // Misc
        minute: "minute",
        minutes: "minutes"
    }
};

// Fonction de traduction
function t(key) {
    const lang = localStorage.getItem('language') || 'fr';
    return translations[lang][key] || key;
}

// Fonction pour changer la langue
function setLanguage(lang) {
    localStorage.setItem('language', lang);
    updatePageLanguage();
}

// Fonction pour mettre à jour tous les textes
function updatePageLanguage() {
    const lang = localStorage.getItem('language') || 'fr';
    
    // Update all elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        element.textContent = t(key);
    });
    
    // Update placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
        const key = element.getAttribute('data-i18n-placeholder');
        element.placeholder = t(key);
    });
    
    // Update button active state
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-lang="${lang}"]`).classList.add('active');
}

// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
    updatePageLanguage();
});
