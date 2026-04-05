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
  }
  
  return path;
}