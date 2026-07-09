export async function POST() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://sbcnav.onrender.com";
  const syncSecret = process.env.SYNC_SECRET || "";

  if (!syncSecret) {
    return Response.json(
      { success: false, message: "SYNC_SECRET is not configured on the frontend server" },
      { status: 500 }
    );
  }

  const response = await fetch(`${apiUrl}/api/internal/sync`, {
    method: "POST",
    headers: {
      "X-Sync-Secret": syncSecret,
    },
  });

  const payload = await response.json().catch(() => null);
  return Response.json(payload ?? { success: false, message: "Invalid sync response", data: null }, {
    status: response.status,
  });
}
