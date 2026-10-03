JSON.stringify(Array.from(new Set(String(document.documentElement.outerHTML).match(/[A-Za-z0-9_\-\.\/:]+\.pdf/gi) || [])).slice(0, 60))
