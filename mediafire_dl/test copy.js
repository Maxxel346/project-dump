function unscrambleURL(scrambledUrl) {
  // Input validation: ensure we have a valid string
  if (!scrambledUrl || typeof scrambledUrl !== "string") {
    return "";
  }

  try {
    // Apply Base64 decoding through our utility function
    return decodeBase64(scrambledUrl);
  } catch (e) {
    console.error("DownloadSecurity: Error unscrambling URL", e);
    return scrambledUrl;
    // Return scrambled URL if unscrambling fails
  }
}

function handleDelayedDownload(element, redirect) {

  //   var scrambledUrl = element.getAttribute("data-scrambled-url");
  var scrambledUrl = "somerandomstringhere";

  var originalUrl = unscrambleURL(scrambledUrl);
  console.log(originalUrl);
}


