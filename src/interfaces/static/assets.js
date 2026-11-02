/**
 * ============================================================================
 * ASSETS VECTORIALES — ESTILO FEDERAL RESERVE & WALL STREET CAPITAL
 * Paleta: Azul Federal (#0038A8 / #0F172A), Rojo Patriótico (#DC2626),
 * Verde Dólar (#059669), Blanco (#FFFFFF) y Negro Carbón (#000000).
 * Sin amarillo: Iconografía sobria, nítida y de alta legibilidad.
 * ============================================================================
 */

export const ICONS = {
  // 1. Tío Sam Institucional Moderno (Sin amarillo, fondo azul marino o plata)
  uncleSam: `
    <svg viewBox="0 0 120 120" class="w-full h-full" fill="none" xmlns="http://www.w3.org/2000/svg">
      <!-- Círculo exterior federal marino -->
      <circle cx="60" cy="60" r="54" fill="#0F172A" stroke="#000000" stroke-width="3"/>
      <circle cx="60" cy="60" r="48" stroke="#334155" stroke-width="1.5" stroke-dasharray="3 3"/>
      
      <!-- Sombrero de Copa Alto -->
      <g>
        <rect x="36" y="16" width="48" height="40" fill="#FFFFFF" stroke="#000000" stroke-width="3"/>
        <!-- Rayas rojas del sombrero -->
        <rect x="43" y="16" width="7" height="40" fill="#DC2626" stroke="#000000" stroke-width="1.5"/>
        <rect x="57" y="16" width="7" height="40" fill="#DC2626" stroke="#000000" stroke-width="1.5"/>
        <rect x="70" y="16" width="7" height="40" fill="#DC2626" stroke="#000000" stroke-width="1.5"/>
        <!-- Banda azul con estrellas blancas -->
        <rect x="34" y="44" width="52" height="12" fill="#1D4ED8" stroke="#000000" stroke-width="2.5"/>
        <polygon points="44,47 45,49.5 47.5,49.5 45.5,51 46.5,53.5 44,52 41.5,53.5 42.5,51 40.5,49.5 43,49.5" fill="#FFFFFF"/>
        <polygon points="60,47 61,49.5 63.5,49.5 61.5,51 62.5,53.5 60,52 57.5,53.5 58.5,51 56.5,49.5 59,49.5" fill="#FFFFFF"/>
        <polygon points="76,47 77,49.5 79.5,49.5 77.5,51 78.5,53.5 76,52 73.5,53.5 74.5,51 72.5,49.5 75,49.5" fill="#FFFFFF"/>
        <!-- Ala del sombrero -->
        <path d="M24 56 C24 54, 96 54, 96 56 L98 60 C88 63, 32 63, 22 60 Z" fill="#1E293B" stroke="#000000" stroke-width="3"/>
      </g>
      
      <!-- Rostro -->
      <path d="M42 60 C42 60, 42 78, 60 82 C78 78, 78 60, 78 60 Z" fill="#F8FAFC" stroke="#000000" stroke-width="2.5"/>
      <path d="M46 64 L54 66" stroke="#000000" stroke-width="2.5" stroke-linecap="round"/>
      <path d="M66 66 L74 64" stroke="#000000" stroke-width="2.5" stroke-linecap="round"/>
      <circle cx="50" cy="68" r="2.5" fill="#000000"/>
      <circle cx="70" cy="68" r="2.5" fill="#000000"/>
      <path d="M60 67 L57 74 L63 74" stroke="#000000" stroke-width="2" fill="none"/>
      
      <!-- Barba blanca -->
      <path d="M50 76 Q60 80 70 76 Q60 74 50 76 Z" fill="#FFFFFF" stroke="#000000" stroke-width="1.5"/>
      <polygon points="54,78 66,78 60,94" fill="#FFFFFF" stroke="#000000" stroke-width="2.5"/>
      
      <!-- Moño patriótico rojo -->
      <path d="M52 94 L60 96 L68 94 L64 102 L56 102 Z" fill="#DC2626" stroke="#000000" stroke-width="2.5"/>
      <circle cx="60" cy="96" r="2.5" fill="#FFFFFF" stroke="#000000" stroke-width="1.5"/>
    </svg>
  `,

  // 2. Águila Calva Federal (Sello Oficial en Azul y Plata)
  baldEagle: `
    <svg viewBox="0 0 120 120" class="w-full h-full" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="60" cy="60" r="54" fill="#F8FAFC" stroke="#0F172A" stroke-width="3"/>
      
      <!-- Alas estilizadas -->
      <path d="M16 46 C28 32, 44 38, 56 46 L50 72 C36 68, 24 62, 16 46 Z" fill="#0F172A" stroke="#000000" stroke-width="2.5"/>
      <path d="M104 46 C92 32, 76 38, 64 46 L70 72 C84 68, 96 62, 104 46 Z" fill="#0F172A" stroke="#000000" stroke-width="2.5"/>
      
      <!-- Cuerpo y cola -->
      <polygon points="50,70 70,70 65,96 55,96" fill="#FFFFFF" stroke="#000000" stroke-width="2.5"/>
      
      <!-- Cabeza blanca y pico plateado -->
      <path d="M52 40 C52 28, 68 28, 68 40 L70 46 L50 46 Z" fill="#FFFFFF" stroke="#000000" stroke-width="2.5"/>
      <polygon points="68,36 82,41 68,44" fill="#CBD5E1" stroke="#000000" stroke-width="2"/>
      <circle cx="60" cy="36" r="2.5" fill="#000000"/>
      
      <!-- Escudo Patriótico Pectoral -->
      <g>
        <path d="M48 50 L72 50 L72 66 C72 76, 60 84, 60 84 C60 84, 48 76, 48 66 Z" fill="#FFFFFF" stroke="#000000" stroke-width="2.5"/>
        <path d="M48 50 L72 50 L72 58 L48 58 Z" fill="#1D4ED8" stroke="#000000" stroke-width="1.5"/>
        <rect x="52" y="58" width="4" height="20" fill="#DC2626"/>
        <rect x="64" y="58" width="4" height="20" fill="#DC2626"/>
      </g>
      
      <!-- Garras con rama de olivo -->
      <line x1="38" y1="90" x2="82" y2="86" stroke="#059669" stroke-width="3" stroke-linecap="round"/>
      <line x1="36" y1="84" x2="84" y2="92" stroke="#000000" stroke-width="2"/>
    </svg>
  `,

  // 3. Sello de Aprobación Federal (Verde Dólar y Marino)
  stampApproved: `
    <svg viewBox="0 0 100 100" class="w-full h-full" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="50" cy="50" r="46" fill="#FFFFFF" stroke="#059669" stroke-width="3"/>
      <circle cx="50" cy="50" r="40" stroke="#059669" stroke-width="1.5" stroke-dasharray="3 2"/>
      <path d="M20 50 L80 50" stroke="#059669" stroke-width="2"/>
      <text x="50" y="36" font-family="'JetBrains Mono', monospace" font-size="9" font-weight="900" fill="#0F172A" text-anchor="middle" letter-spacing="1">FEDERAL RESERVE</text>
      <text x="50" y="66" font-family="'JetBrains Mono', monospace" font-size="12" font-weight="900" fill="#059669" text-anchor="middle" letter-spacing="1">APPROVED</text>
      <text x="50" y="80" font-family="'JetBrains Mono', monospace" font-size="7" font-weight="800" fill="#64748B" text-anchor="middle">CLEARED 2026</text>
    </svg>
  `,

  // 4. Código de Barras de Acceso
  barcodeSvg: `
    <svg viewBox="0 0 160 50" class="w-full h-full" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="160" height="50" fill="#FFFFFF"/>
      <rect x="10" y="6" width="4" height="30" fill="#0F172A"/>
      <rect x="18" y="6" width="2" height="30" fill="#0F172A"/>
      <rect x="23" y="6" width="6" height="30" fill="#0F172A"/>
      <rect x="33" y="6" width="3" height="30" fill="#0F172A"/>
      <rect x="39" y="6" width="5" height="30" fill="#0F172A"/>
      <rect x="48" y="6" width="2" height="30" fill="#0F172A"/>
      <rect x="54" y="6" width="7" height="30" fill="#0F172A"/>
      <rect x="65" y="6" width="2" height="30" fill="#0F172A"/>
      <rect x="71" y="6" width="5" height="30" fill="#0F172A"/>
      <rect x="80" y="6" width="3" height="30" fill="#0F172A"/>
      <rect x="87" y="6" width="6" height="30" fill="#0F172A"/>
      <rect x="97" y="6" width="2" height="30" fill="#0F172A"/>
      <rect x="103" y="6" width="5" height="30" fill="#0F172A"/>
      <rect x="112" y="6" width="7" height="30" fill="#0F172A"/>
      <rect x="123" y="6" width="3" height="30" fill="#0F172A"/>
      <rect x="130" y="6" width="4" height="30" fill="#0F172A"/>
      <rect x="138" y="6" width="8" height="30" fill="#0F172A"/>
      <rect x="150" y="6" width="2" height="30" fill="#0F172A"/>
      <text x="80" y="44" font-family="'JetBrains Mono', monospace" font-size="9" font-weight="800" fill="#0F172A" text-anchor="middle" letter-spacing="3">FED-MED-99420</text>
    </svg>
  `,

  // 5. Icono Hospital General (PostgreSQL) - Azul Federal
  hospital: `
    <svg viewBox="0 0 48 48" class="w-full h-full" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="6" y="8" width="36" height="34" rx="2" fill="#1D4ED8" stroke="#0F172A" stroke-width="2.5"/>
      <rect x="12" y="14" width="24" height="22" fill="#FFFFFF" stroke="#0F172A" stroke-width="2"/>
      <rect x="21" y="18" width="6" height="14" fill="#DC2626"/>
      <rect x="17" y="22" width="14" height="6" fill="#DC2626"/>
      <polygon points="6,8 24,1 42,8" fill="#0F172A" stroke="#0F172A" stroke-width="2.5"/>
    </svg>
  `,

  // 6. Icono Centro Pediátrico (MySQL) - Azul Cyan / Verde
  pediatrico: `
    <svg viewBox="0 0 48 48" class="w-full h-full" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="24" cy="24" r="18" fill="#E0F2FE" stroke="#0F172A" stroke-width="2.5"/>
      <circle cx="24" cy="18" r="8" fill="#FFFFFF" stroke="#0F172A" stroke-width="2"/>
      <circle cx="21" cy="17" r="1.5" fill="#0F172A"/>
      <circle cx="27" cy="17" r="1.5" fill="#0F172A"/>
      <path d="M21 21 Q24 24 27 21" stroke="#DC2626" stroke-width="2" fill="none"/>
      <rect x="18" y="28" width="12" height="10" rx="3" fill="#0284C7" stroke="#0F172A" stroke-width="2"/>
    </svg>
  `,

  // 7. Icono Laboratorio Clínico (MongoDB NoSQL) - Verde Esmeralda
  laboratorio: `
    <svg viewBox="0 0 48 48" class="w-full h-full" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M19 6 L29 6 M22 6 L22 16 L10 38 C8 42, 12 44, 16 44 L32 44 C36 44, 40 42, 38 38 L26 16 L26 6" fill="#ECFDF5" stroke="#0F172A" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M13 36 C19 32, 29 38, 35 34" stroke="#059669" stroke-width="2.5"/>
      <circle cx="20" cy="40" r="2" fill="#059669"/>
      <circle cx="28" cy="38" r="1.5" fill="#059669"/>
    </svg>
  `,

  // 8. Icono Clínica Odontológica (Firestore Cloud) - Púrpura / Índigo Clínico
  odontologia: `
    <svg viewBox="0 0 48 48" class="w-full h-full" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M14 10 C18 8, 20 12, 24 12 C28 12, 30 8, 34 10 C38 12, 40 20, 38 28 C36 34, 33 42, 29 44 C27 45, 25 38, 24 38 C23 38, 21 45, 19 44 C15 42, 12 34, 10 28 C8 20, 10 12, 14 10 Z" fill="#F8FAFC" stroke="#0F172A" stroke-width="2.5" stroke-linejoin="round"/>
      <circle cx="17" cy="18" r="1.5" fill="#1D4ED8"/>
      <circle cx="31" cy="18" r="1.5" fill="#1D4ED8"/>
      <path d="M20 28 Q24 32 28 28" stroke="#1D4ED8" stroke-width="2" fill="none"/>
    </svg>
  `
};
