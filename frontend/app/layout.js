import "./globals.css";

export const metadata = {
  title: "ALIBI — the town that remembers",
  description: "A detective game where the NPCs never forget. Powered by Cognee.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Special+Elite&family=Playfair+Display:ital,wght@0,500;0,700;1,500&family=IBM+Plex+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="grain" />
        {children}
      </body>
    </html>
  );
}
