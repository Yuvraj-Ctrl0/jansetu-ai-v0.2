/** Question definitions shared by the eligibility checker and the profile form. */
const opts = (list) => (list || []).map((o) => (typeof o === 'string' ? { value: o, label: o } : o));

export function eligibilitySteps(meta) {
  return [
    {
      id: 'about',
      title: 'About you',
      intro: 'Basic details decide most schemes. Skip anything you are not sure about.',
      fields: [
        { key: 'age', label: 'Age', type: 'number', min: 0, max: 120, suffix: 'years' },
        { key: 'gender', label: 'Gender', type: 'select', options: opts(meta.genders) },
        { key: 'state', label: 'State or Union Territory', type: 'select', options: opts(meta.states) },
        { key: 'area', label: 'Where do you live?', type: 'choice', options: opts(meta.areas) },
        { key: 'social_category', label: 'Social category', type: 'select', options: opts(meta.social_categories),
          hint: 'Only used for schemes reserved for SC, ST or OBC.' },
        { key: 'marital_status', label: 'Marital status', type: 'select', options: opts(meta.marital_statuses) },
        { key: 'disability_status', label: 'Do you have a disability certificate?', type: 'yesno' },
      ],
    },
    {
      id: 'work',
      title: 'Work and income',
      intro: 'Income limits and occupation rules apply to loans, pensions and scholarships.',
      fields: [
        { key: 'occupation', label: 'Main occupation', type: 'select', options: opts(meta.occupations) },
        { key: 'annual_income', label: 'Yearly family income', type: 'number', min: 0, prefix: '₹',
          hint: 'Total income of everyone in your family in a year.' },
        { key: 'student_level', label: 'Are you studying right now?', type: 'select', options: opts(meta.student_levels) },
        { key: 'income_tax_payer', label: 'Do you pay income tax?', type: 'yesno',
          hint: 'Choose Yes if you have ever filed and paid income tax.' },
        { key: 'organised_sector_member', label: 'Are you a member of EPFO, ESIC or NPS?', type: 'yesno',
          hint: 'Usually Yes if PF is cut from your salary.' },
        { key: 'has_bank_account', label: 'Do you have a savings bank or post office account?', type: 'yesno' },
      ],
    },
    {
      id: 'home',
      title: 'Family and home',
      intro: 'These decide housing, food, pension and family-support schemes.',
      fields: [
        { key: 'bpl_card', label: 'Do you have a BPL, Antyodaya or priority household ration card?', type: 'yesno' },
        { key: 'govt_employee_in_family', label: 'Is anyone in your family a government employee?', type: 'yesno' },
        { key: 'owns_agri_land', label: 'Does your family own farm land?', type: 'yesno' },
        { key: 'land_hectares', label: 'How much farm land?', type: 'number', min: 0, step: '0.1', suffix: 'hectares',
          hint: '1 hectare is about 2.47 acres.', showIf: (a) => a.owns_agri_land === true },
        { key: 'owns_pucca_house', label: 'Does your family own a pucca (permanent) house?', type: 'yesno' },
        { key: 'has_lpg_connection', label: 'Does your home already have an LPG gas connection?', type: 'yesno' },
        { key: 'pregnant_or_lactating', label: 'Are you pregnant or breastfeeding a baby?', type: 'yesno', transient: true,
          hint: 'Used only for this check. It is never saved.', showIf: (a) => a.gender === 'Woman' },
        { key: 'daughter_below_10', label: 'Do you have a daughter younger than 10?', type: 'yesno', transient: true },
      ],
    },
  ];
}

export function profileSections(meta) {
  const steps = eligibilitySteps(meta).map((s) => ({ ...s, fields: s.fields.filter((f) => !f.transient) }));
  return [
    {
      id: 'contact',
      title: 'Your name and place',
      fields: [
        { key: 'full_name', label: 'Full name', type: 'text', max: 120 },
        { key: 'district', label: 'District', type: 'text', max: 120 },
        { key: 'education_level', label: 'Highest education', type: 'select', options: opts(meta.education_levels) },
        { key: 'employment_status', label: 'Employment status', type: 'select', options: opts(meta.employment_statuses) },
        { key: 'household_size', label: 'People in your household', type: 'number', min: 1, max: 50 },
        { key: 'interests', label: 'What kind of help are you looking for?', type: 'text', max: 500, wide: true,
          placeholder: 'For example: education loan, farming, starting a shop' },
      ],
    },
    ...steps,
  ];
}

export const TRANSIENT_KEYS = ['pregnant_or_lactating', 'daughter_below_10'];

export function answeredCount(answers) {
  return Object.values(answers).filter((v) => v !== '' && v !== null && v !== undefined).length;
}
