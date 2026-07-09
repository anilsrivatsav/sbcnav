import "./globals.css";

export const metadata = {
  title: "Rail Dashboard",
  description: "Stations, catering units, and sanctioned works dashboard",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
