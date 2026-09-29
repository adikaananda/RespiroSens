/* ==========================================================================
   app.js — bootstrap. Loaded LAST, after every other module has defined its
   functions. Keep this file tiny: it should only ever call functions, never
   define new ones.
   ========================================================================== */

(async function bootstrap(){
  await loadLoginScreen();

  // If a token is already stored (page refresh), skip straight back into the app.
  if (authToken && currentUser) {
    currentRole = currentUser.role;
    enterApp();
  }
})();
