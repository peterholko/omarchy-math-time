// The original Math Time's white sheet and ink palette, with timed practice labels.
var PALETTE = {
  paper: "#ffffff", ink: "#1c1c1e", inkSoft: "#6b6b73", rule: "#d9d9de",
  mark: "#2f6fed", good: "#1e8e3e", bad: "#c62828"
}
function clock(seconds) {
  var value = Math.max(0, Math.ceil(Number(seconds) || 0))
  return Math.floor(value / 60) + ":" + ("0" + value % 60).slice(-2)
}
function errorText(error) {
  switch (error) {
    case "upgrade_required": return "A parent needs to upgrade Math Time's service with setup --upgrade."
    case "bad_password": return "That parent password wasn't accepted. Please try again."
    case "try_later": return "Please wait a moment before trying the parent password again."
    case "school_or_locked": return "Practice needs an unlocked desktop and available School Mode status."
    case "use_digits": return "Type your answer using digits."
    case "acknowledgement_required": return "Read the correct answer, then choose Continue."
    case "not_reviewing": return "Answer the question before continuing."
    case "stale_question": return "The question changed. Please answer the one shown."
    case "not_enrolled": return "A parent needs to run Math Time setup for this account."
    case "not_practising": return "Practice is paused. Your progress is saved."
    default: return "Math Time's practice service is unavailable. Your progress is saved; reconnecting…"
  }
}
if (typeof module !== "undefined") module.exports = {PALETTE: PALETTE, clock: clock, errorText: errorText}
