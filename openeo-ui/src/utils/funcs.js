export function buildUrl(path) {
  // Detects if Vite is being used by checking the DEV environment variable. 
  // If it is, it assumes that the backend is running on a different host 
  // and constructs the URL accordingly. Otherwise, it returns the path as is, 
  // which would work in a production environment where the frontend and 
  // backend are served from the same origin.

  const isVite = !!import.meta.env.DEV;
  
  if (isVite) {
    console.log("UI dev mode enabled",isVite,path);
    return `http://192.168.123.50/${path}`;
  } else {
    console.log("URL:",path);
  }
  
  return path;
}

export function getCurrencyConfig() {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone ?? "";

  if (tz.startsWith("Pacific/Auckland") || tz.startsWith("NZ"))
    return { locale: "en-NZ", currency: "NZD", symbol: "NZ$" };

  if (tz.startsWith("Australia/"))
    return { locale: "en-AU", currency: "AUD", symbol: "A$" };

  const ukZones = [
    "Europe/London", "Europe/Belfast", "Europe/Jersey",
    "Europe/Guernsey", "Europe/Isle_of_Man",
  ];

  if (ukZones.includes(tz))
    return { locale: "en-GB", currency: "GBP", symbol: "£" };

  if (tz.startsWith("Europe/"))
    return { locale: "de-DE", currency: "EUR", symbol: "€" };

  if (
    tz.startsWith("America/") ||
    tz.startsWith("US/") ||
    ["EST", "PST", "CST", "MST"].includes(tz)
  )
    return { locale: "en-US", currency: "USD", symbol: "$" };

  // Fallback → GBP
  return { locale: "en-GB", currency: "GBP", symbol: "£" };
}


export function formatCurrency(amount,CURRENCY = getCurrencyConfig()) {
  return new Intl.NumberFormat(CURRENCY.locale, {
    style: "currency",
    currency: CURRENCY.currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount ?? 0);
}
