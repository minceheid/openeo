<div id=output></div>
{% include 'html_footer.tpl' %}
  <script>const endpoints = ["getstatus", "getconfig", "debugdata"];

    // recursive pretty-printer that handles multiline text
    function formatJson(obj, indent = 2) {
      if (typeof obj === "string") {
        if (obj.includes("\n")) {
          // wrap multiline strings in <pre> style text
          return obj;
        }
        return obj;
      }
      return JSON.stringify(obj, null, indent);
    }

    async function fetchAndDisplay(endpoint) {
      const container = document.getElementById("output");

      // create a wrapper div for this endpoint
      const block = document.createElement("div");
      block.className = "endpoint-block";

      // title
      const title = document.createElement("h2");
      title.textContent = endpoint;
      block.appendChild(title);

      // result placeholder
      const pre = document.createElement("pre");
      pre.textContent = "Loading...";
      block.appendChild(pre);

      container.appendChild(block);

      try {
        const response = await fetch(endpoint);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        // stringify normally
        let jsonString = JSON.stringify(data, null, 2);

        // unescape real linefeeds for display
        jsonString = jsonString.replace(/\\n/g, "\n");

        pre.textContent = jsonString;
      } catch (err) {
        pre.textContent = `Error: ${err.message}`;
        pre.classList.add("error");
      }
    }

    // loop through endpoints and build UI dynamically
    endpoints.forEach(fetchAndDisplay);
  </script>