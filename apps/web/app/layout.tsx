import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ketabdaneh",
  description: "Branch operations management system for a Ketabdaneh branch",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
