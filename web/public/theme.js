// Apply the saved theme before the app renders to avoid a light flash.
(() => {
  let theme = 'dark'
  try {
    const saved = localStorage.getItem('insightflow-theme')
    if (saved === 'light' || saved === 'dark') theme = saved
  } catch { /* Storage can be unavailable in private browser contexts. */ }
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
})()
