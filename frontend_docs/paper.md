# Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy

Preprint, compiled March 31, 2025

Felix M. Schmitt-Koopmann ID 1, 2∗, Elaine M. Huang ID 2, Hans-Peter Hutter ID 1, and Alireza Darvishy ID 1

1Institute of Computer Science, ZHAW, 8401 Winterthur, Switzerland 2People and Computing Lab, University of Zurich, 8050 Zurich, Switzerland

## Abstract

PDF inaccessibility is an ongoing challenge that hinders individuals with visual impairments from reading and navigating PDFs using screen readers. This paper presents a step-by-step process for both novice and experienced users to create accessible PDF documents, including an approach for creating alternative text for mathematical formulas without expert knowledge. In a study involving nineteen participants, we evaluated our prototype PAVE 2.0 by comparing it against Adobe Acrobat Pro, the existing standard for remediating PDFs. Our study shows that experienced users improved their tagging scores from 42.0% to 80.1%, and novice users from 39.2% to 75.2% with PAVE 2.0. Overall, fifteen participants stated that they would prefer to use PAVE 2.0 in the future, and all participants would recommend it for novice users. Our work demonstrates PAVE 2.0’s potential for increasing PDF accessibility for people with visual impairments and highlights remaining challenges.

Keywords Accessibility, PDF, Tagged PDF, PDF/UA, AI, User Study, Screen Readers

## 1 Introduction

Many people with visual impairments rely on screen readers to access and read PDFs. Unfortunately, research has shown that only a tiny percentage of the trillions of PDF documents available are accessible for individuals who use screen readers and meet the PDF Universal Access (UA) standard [45]. This means that people with visual impairments cannot properly read most PDFs with screen readers, posing a significant problem — especially in STEM fields, where PDF is the dominant format [5]. Consequently, 2.4% of the US population is not able to easily read most scientific PDFs [26]. This presents an extra barrier for people with visual impairment wishing to pursue studies or careers in STEM fields [13] which contributes to the underrepresentation of people with disabilities in research [16].

The importance of this issue is underscored by several laws and resolutions created to ensure access to public documents for everybody. The oldest of these is the US Rehabilitation Act Section 508 of 1998 [44]. It requires US federal departments and agencies to make electronic and information technology accessible to people with disabilities. Moreover, the 2008 United Nations Convention on the Rights of Persons with Disabilities [43] and the European Accessibility Act [11] of 2019 require that critical products and services be usable by people with disabilities.

The discrepancy between these legal regulations and the continued lack of accessibility of PDFs documents can be attributed in large part to the lack of awareness regarding PDF accessibility and the challenge of making PDF documents accessible. The CHI conferences have made significant efforts to promote accessibility in CHI papers by providing templates, guidelines, and services [5]. However, the current processes for making PDFs accessible are still time-consuming and error-prone, and require expert knowledge [17], challenges that many authors have likely experienced. As a result, our analysis reveals that conference papers often include tags, but the accuracy of the tags need to be improved.

Hence, there is a need for methods and tools that allow people to remediate PDFs with a high degree of accessibility [5, 17, 33]. Such tools should not require that individuals have substantial specialized knowledge or invest large amounts of time to use them successfully. We developed a novel PDF remediation process with eight distinct steps to prevent users from becoming overwhelmed by the complexities of PDF accessibility details. One of our goals was to understand how our method affects the PDF remediation process from the user perspective, as well as how it affects the accessibility of the PDFs themselves. To evaluate our process, we conducted a user study involving nineteen participants with varying levels of experience in PDF remediation. Participants remediated a PDF once with our prototype and once with the industry standard tool, Adobe Acrobat Pro. It showed that our process allows novice as well as experienced users to increase the tag accuracy of their PDFs by around 90% and fifteen of nineteen participants stated that they would like to use our tool in the future.

In this work, we present the following major contributions: 1) A user study to evaluate our step-by-step PDF remediation process, 2) a novel AI-based method to automatically create alternative texts for mathematical formulas, and 3) a novel accessibility score with thirteen criteria to reliably evaluate the tag accuracy of a PDF.

The remainder of the paper is organized as follows: Section 2 explores the related work. Section 3 presents the developed process and our prototype, PAVE 2.0. Section 4 presents the design of the user test. The results of the user test are presented in Section 5 and we discuss the results in Section 6. Lastly, Section 8 contains concluding remarks.

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 2 2

## 2 Related Work

An accessible PDF can be created in two ways. The first method involves exporting an accessible PDF directly from the document editing software, provided that the software has an accessible PDF export option. However, not all document editors have this feature, and the author has to follow specific guidelines when creating the document to ensure that it is exported correctly as an accessible PDF. The second option is PDF remediation in which the author modifies an existing PDF to make it accessible. We focus on the PDF remediation method in this work because it is applicable regardless of the process used to create the PDF originally. This process is therefore valuable for making new PDFs accessible at time of their creation, but also for potentially making the vast quantity of inaccessible PDFs already in existence accessible to individuals who use screen readers as well. However, the complexity of the PDF remediation process has contributed directly to the current situation in which hardly any scientific PDFs are accessible, as the following research shows.

Wang et al. [45] automatically assessed over 11,000 scientific PDFs, published between 2010 and 2019, and found that only 2.4% of the PDFs satisfied all their accessibility criteria. Nganji et al. [28] manually analyzed 200 articles from four journals between 2014 and 2018. They found that only 15.5% of the documents contained tags. Darvishy et al. [8] investigated 2,500 papers in repositories of five German-speaking universities in Switzerland from 2018 to 2022 in a semi-automatic way and found that only 11.5% of the papers contained tags. Pierrès et al. [32] examined 8,000 papers from four large scientific repositories mainly from 2023 and 2024 and found that papers that contained at least one tag and were marked as tagged comprised only 0.9% of the papers for Wiley and 16.2% for Elsevier. Even though the accessibility of scientific literature has improved in recent years, the vast majority of research literature is still not accessible to everyone.

This lack of document accessibility is not only a problem in regard to scientific literature. Drye et al. [10] conducted a study to understand the accessibility of business communication materials. The study revealed that one-third of the participants could not define what accessibility of documents means. Additionally, half of the participants did not know how to create an accessible document. Similar to the findings of Rajkumar et al. [17], this highlights how the lack of awareness of accessibility is one of the key reasons why documents are not made accessible.

Bigham et al. [5] presented their experience when trying to make conference PDFs accessible. They highlighted that current tools for this task are too complicated and not usable for inexperienced users. Similarly, Rajkumar et al. [17] found that most researchers and practitioners in STEM fields are unhappy with the existing tools. For this reason, user-friendly tools for creating accessible documents are a major necessity to improve the accessibility of scientific and other literature.

The related work on methods for making PDFs accessible can be categorized into three groups. The first group involves converting PDFs into a more accessible format. For instance, Wang et al. [45] developed SciA11y, a method to transform a PDF into an accessible HTML. This is especially beneficial for making existing PDFs accessible without manual work. However, conversion errors do occur and are not detected which is problematic. Besides SciA11y, there are many other tools available that can convert PDFs into HTML, as shown in the evaluation by Pathirana et al. [29].

The second group considers how to check PDF accessibility. One of the most popular tools for this is the PDF Accessibility Checker (PAC) [42]. PAC allows users to analyze and reveal accessibility issues in a PDF but these cannot be corrected directly in the tool. Even more important, checkers are limited to machine-testable criteria which do not cover all important accessibility aspects, e.g., the correct tagging of headers or the reading order [19].

The third group comprises interactive tools that allow users to make PDFs accessible (PDF remediation). The most popular tool is Adobe Acrobat Pro [1]. Other professional PDF remediation tools are, e.g., CommonLook PDF [7], Axes4 PDF [2], and Foxit Reader [14]. However, the workflows between these tools differ only slightly. They utilize an accessibility checker as a guide for the user, and the user can edit the structure tree directly. Additionally, they offer an automatic tagging feature that creates tags for the entire document.

Doblies et al. [9] developed the web application PAVE in 2014 upon which our prototype (PAVE 2.0) is based. The idea of PAVE was to provide a simple, semi-automatic process for nonexperts to remediate PDFs. A comparison study with Adobe Acrobat Pro [17] revealed that a semi-automatic tool like PAVE is necessary to foster PDF accessibility, but PAVE at that time did not meet user expectations regarding intuitiveness or user experience. They found that a big part of the user frustration was that the participants did not know what was auto-tagged by PAVE and how to override it. Pradhan et al. [33] developed the Ally prototype to improve the user experience of remediation tools using best practices from HCI research. The major improvement to existing tools was that the user no longer interacted directly with the PDF structure tree which represents the logical structure of the content of a PDF. Instead, Ally splits the process into multiple logical subtasks to give the user more guidance. Their prototype presented user interfaces for four subtasks (regions, headers, reading order, and tables), but not for the complete PDF remediation process. This work incorporates the findings of Pradhan et al. and extends it to a complete AI-supported PDF remediation process.

## 3 Interface Design of PAVE 2.0

Our goal was to develop a semi-automatic process that makes the PDF remediation process more intuitive and easier while avoiding direct user interaction with the complex PDF structure tree. Inspired by Pradhan et al. [33], we developed a PDF remediation process with eight steps.

Four of these steps (Region, Reading Order, Heading Structure, and Meta Information) are necessary for every PDF, regardless of its content. We decided to split the content-independent tasks into four distinct steps to ensure that each step focuses on a single, clearly defined task. The remaining four steps (Tables, Lists, Figures, and Mathematical Formulas) are content-dependent, reflecting their common presence in scientific PDFs. Although additional content-dependent steps could be considered, we identified these four steps as the most relevant for scientific papers.

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 3

The final PDF tag structure is then constructed by combining the information from each of these steps.

This step-by-step approach ensures a logical workflow and prevents the user from creating invalid tags or invalid nesting of tags in the PDF structure tree. In contrast to most PDF remediation tools, we decided not to integrate an accessibility report or check in the prototype as it may foster a misleading impression of accessibility [19]. We want to note that the first three steps (Region, Reading Order, Heading Structure) are inspired by Pradhan et al. [33].

The user interface for each of the steps is split into three parts (see Figure 1). On the left side is the navigation pane for all eight steps. The workspace for each step is located in the center pane. On the right side, the page view shows the current PDF page with the tagged regions. At upper left of the workspace area there is a brief description of what the user should do in this step, what the page view is showing, and which features are available.

The page view always shows one rendered page of the PDF at a time with status information at the top, depending on the step. The user can zoom in and out of the page. Depending on the step, the user can hide different aspects of the visualization to reduce visual clutter and cognitive load [41].

The user interface was developed using the ReactJS library [23]. It was designed with accessibility as a priority, e.g., using a high-contrast color palette. However, we overlooked a problematic red-green color combination in Step 2 which a participant highlighted later. While the prototype is not fully accessible (particularly the drawing functionalities) to streamline development, achieving complete accessibility remains essential for the production version. The PDF is modified and parsed on the back end, which is based on the back end of the original PAVE tool [51]. In the following section, we explain each of the eight steps of the PAVE 2.0 remediation process.

### 3.1 Step 1 - Regions

In the first step of the PAVE 2.0 process, the user is required to identify the different regions on each page of the PDF, such as paragraphs, headings, lists, formulas, figures, captions, artifacts, and tables (see Figure 1). Users are provided with two options to define regions. Firstly, users can select untagged content such as text, images, or drawing elements (PDF operators) within the PDF using the cursor in the page view pane to define a new tagged region. Alternatively, they can opt for automatic detection of the regions. The automatic region detection uses a combination of two AI models. For detecting formulas, we trained a Generalized Focal Loss V2 object detector with a ResNetXt101 backbone [21] with the FormulaNet dataset [36]. Our trained model can detect locations of mathematical formulas with an accuracy of 0.89 mAP. To detect headings, text, tables, figures, and lists, a second model was trained with the same architecture and the PubLayNet dataset [52], reaching an accuracy of 0.90 mAP. Each PDF operator is assigned to the predicted bounding box with the highest overlap. If two bounding boxes yield similar overlap, the bounding box with the higher score is selected. If a PDF operator does not overlap with a bounding box, it is marked as Artifact. This ensures that all PDF operators are marked. The detected regions are outlined in the page view with the region type name in the top right corner of the outline box. The color of the outline boxes indicates the type of region for an easy visual overview [49].

To edit existing regions, the user has two options: they can select one or multiple regions and delete the region tags, which turns the corresponding PDF operators back to untagged. They can also resize an existing region by dragging one of the eight resize points. Information about a selected region is shown in the workspace. There, the user can check the text assigned to the region and change the region type using a drop-down menu. This kind of annotation is widely used in annotation tools such as PAWLS [27] or PDFAnno [39]. In contrast to Pradhan et al. [33], the user does not have to define the heading levels up front, which is difficult before all headings have been defined.

### 3.2 Step 2 - Reading Order

In the second step, the user defines the reading order for each page, i.e. the logical order in which the regions defined in the previous step should be read by a screen reader. Research has shown that reading order is crucial for individuals who use screen readers and an incorrect reading order can lead to frustration [20, 17].

The reading order is visualized on the page view as a directed line graph with numbers, as well as an ordered list in the workspace pane (see Figure 2). The user has two options to modify the reading order. First, they can simply draw a line into the PDF page shown the page view to define the desired reading order. If the user selects this option, all regions are first marked in red. The user can then define the reading order by drawing a curved line over the regions in the order they should be read. If the cursor crosses a region, the region text is marked green, and a green bounding box appears. If the user has not selected all regions with the drawn line graph, the skipped regions are appended to the reading order in their previous order. Alternatively, to modify the reading order only slightly, the user can move elements in the reading order list in the workspace pane. Additionally, the user can change a region into an artifact if it should not be read out at all. The color codes for the bounding boxes are the same as in Step 1.

### 3.3 Step 3 - Heading Levels

In the third step, the user defines the heading structure of all headings in the document. Headings allow individuals who use screen readers to easily navigate in a document. Research has shown that headings are the most used option to navigate websites [47]. Hence, we added an explicit step for defining the heading structure and did not integrate it with Step 1, as Pradhan et al. did.

The heading structure of the complete document is visualized as a list in the workspace pane. There, the user can adjust each heading level using the corresponding drop-down menu. The choice of heading levels is restricted to those that adhere to a valid heading structure. The user can also allow the system to automatically detect the heading levels based on their text size (also changes existing heading levels). If an uploaded PDF already contains an invalid heading structure, the heading structure is automatically updated to a valid structure. This means that <H> tags are automatically changed to <H1>. Additionally,

![](images/5d8a6ebb1eda49f59b9dc5ac7518e8b485af48e33e8ac085ce3440fb9ed3938d.jpg)

<details>
<summary>text_image</summary>

PAVE 2.0
Step 1 of 8: Define Regions
In this step, you can refine and adjust regions in the entire document. Utilize the page navigation located below to navigate through the document. A region categorizes PDF elements, each labeled with a specific type indicating its semantic meaning. On the right, you have the page view with the current regions. The title reveals the number of elements that need to be tagged on the page. You can show and hide the labels of the regions and the artifact regions. Additionally, you can zoom in and out of the page. On the left, you can manipulate the regions. To modify a region, select a region within the page view and change its size, type, or remove it entirely. If you checked all pages in the document use the "Next Step" button to get to step 2.
Possible Actions
Detect Regions: Automatically detect regions in the current page. It will overwrite existing regions of the current page.
New Regions: Draw a new region on the page view.
Delete All Regions: Remove all regions from the current page in a single action.
Hints
Next Step
Pages
1 /3
(2 Pages not checked)
Detect Regions
New Region
Delete All
1 Region Selected
Region Type Paragraph
Content
BEN TROVATO, Institute for Clarity in Documentation, USALARS THERRVALD, The Therväld Group, Iceland/VALERIE BÉRANGER, Irina Paris-Rocquencourt, France/PARNA PATEL Rajiv GandN University, India/JUIFEN CHAN, Tsinghua University, China/CHARLES PALMER, Palmer Research Laboratories, USA/JOHN SMITH, The Therväld Group, Iceland/JULUS P. KUMQUAT, The Kumquat Consortium, USA
Delete Region
Page 1 (0 elements not tagged)
Header
The Name of the Title Is Hand
BEN TROVATO, Institute for Clarity in Documentation, USALARS TH RIVALD, The Therväld Group, Iceland/VALERIE BÉRANGER, Irina Paris-Rocquencourt, France/PARNA PATEL Rajiv GandN University, India/JUIFEN CHAN, Tsinghua University, China/CHARLES PALMER, Palmer Research Laboratories, USA/JOHN SMITH, The Therväld Group, Iceland/JULUS P. KUMQUAT, The Kumquat Consortium, USA
Paragraph
What and not described by Eq. Accounts are presented for any journal in publication by ACM in accordance with regulations or regulations specified in this report.
Paragraph
What and not described by Eq. Accounts are presented for any journal in publication by ACM in accordance with regulations or regulations specified in this report.
Paragraph
What and not described by Eq. Accounts are presented for any journal in publication by ACM in accordance with regulations or regulations specified in this report.
Paragraph
What and not described by Eq. Accounts are presented for any journal in publication by ACM in accordance with regulations or regulations specified in this report.
Paragraph
What and not described by Eq. Account is presented for any journal in publication by ACM in accordance with regulations or regulations specified in this report.
Paragraph
What and not described by Eq. Account is presented for any journal in publication by ACM in accordance with regulations or regulations specified in this report.
Paragraph
What and not described by Eq. Account is presented for any journal in publication by ACM in accordance with regulations or regulations specified in this report.
Paragraph
What and not described by Eq. Account is presented for any journal in publication by ACM in correspondence with the same journal's own version of the original document.
Paragraph
What and not described by Eq. Account is presented for any journal in publication by ACM in correspondence with the same journal's own version of the original document.
Paragraph
What and not described by Eq. Account is presented for any journal in publication by ACM in correspondence with the same journal's own version of the original document.
Paragraph
What and not described by Eq. Account is presented for any journal in publication by ACM in correspondence with the same journal's own version of the original document.

Paragraph
What and not described by Eq. Account is presented for any journal in publication by ACM in correspondence with the same journal's own version of the original document.

Paragraph
What and not described by Eq. Account is presented for any journal in publication by ACM in correspondence with the same journal's own version of the original document.

Paragraph
What and not described by Eq. Account is presented for any journal in publication by ACM in correspondence with the same journal's own version of the original document.

Header
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Header
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
Paragraph
</details>

Figure 1: Screenshot of Step 1 (regions) in PAVE 2.0. The interface contains three interface panes from left to right: step navigation, workspace, page view.

![](images/05b1bc5840182304b58aec976dbe79f96a55c572ffa68524bc8826435fe25c7e.jpg)

<details>
<summary>text_image</summary>

Step 2: Define Reading Order
In this step, you can adjust the reading order for each page in the entire document. The reading order sets the sequence in which a document's content is read by the screen reader. The reading order is visualized on the right in the page view or below as a list. You can modify the reading order, by drawing the reading order in the page view or by moving the regions in the list below.
Possible Actions
Draw Reading Order: Draw the reading order as a line on the page view.
Next Step
Pages
1 /3
(2 Pages not checked)
Draw Reading Order
Reading Order
is read aloud by
screen reader
1: Header The Name of the Title Is Hope
2: Paragraph BEN TROVATO•Institute for Clarity in Documentatio
3: Paragraph A clear and well-documented LATX document is prese
4: Paragraph CCS Concepts--Do Not Use This Code->Generate the Co
5: Paragraph Additional Key Words and Phrases: Do, Not, Us, Thi
6: Paragraph ACM Reference Format:
7: Paragraph Ben Trovato, Lars Thervald, Valerie Béranger, Apar
8: Header 1 INTRODUCTION
9: Paragraph ACM's consolidated article template, introduced in
10: Paragraph insight and instruction into more recent changes t
11: Paragraph The "acmart" document class can be used to prepare
12: Formula ∑∞/∫±2×≡=±0/≡0=0
13: Header 2 TEMPLATE OVERVIEW
14: Paragraph As noted in the introduction, the "acmart" document
15: Header 2.1 Template Styles
16: Paragraph The primary parameter given to the "acmart" document
Page 1
The Name of 1 Title Is Hope
EN TROVATO•Institute for Clarity in Documentation, USA
LARS TH RVALD, THE Thervald Group, Iceland
VALERIE BÉRANGER, Canada Paris-Récopancourt, France
PARNA PATEL, Rajiv Gogh University, India
HUIFEN CHAN, Ningbo University, China
CHARLES PALMER, Paper Research Laboratories, USA
JOHN SMITH, The Thervald Group, Iceland
JULUS P. KUMOUST, The Korea
New and new documentation is required to provide any information from publication to publish and create a new document that is available. Based on the "national literature," this article presents an update many of the contents were used as well as many of the formering features as further may not be used in the publication of the documents that are found.
3. Paragraph The Concept - Do Not Use New Chinese Texts and New Paper Generation The Book for Our Use, In contrast to the English Language (English Language). It is also important to include all relevant articles.
4. Paragraph The Name of the Title Is Hope
5. Paragraph The Name of the Title Is Hope
6. Paragraph The Name of the Title Is Hope
7. Paragraph The Name of the Title Is Hope
8. Paragraph The Name of the Title Is Hope
9. Paragraph The Name of the Title Is Hope
10. Paragraph The Name of the Title Is Hope
11. Paragraph The Name of the Title Is Hope
12. Paragraph The Name of the Title Is Hope
13. Paragraph The Name of the Title Is Hope
14. Paragraph The Name of the Title Is Hope
15. Paragraph The Name of the Title Is Hope
16. Paragraph The Name of the Title Is Hope
17. Paragraph The Name of the Title Is Hope
18. Paragraph The Name of the Title Is Hope
19. Paragraph The Name of the Title Is Hope
20. Paragraph The Name of the Title Is Hope
21. Paragraph The Name of the Title Is Hope
22. Paragraph The Name of the Title Is Hope
23. Paragraph The Name of the Title Is Hope
24. Paragraph The Name of the Title Is Hope
25. Paragraph The Name of the Title Is Hope
26. Paragraph The Name of the Title Is Hope
27. Paragraph The Name of the Title Is Hope
28. Paragraph The Name of the Title Is Hope
29. Paragraph The Name of the Title Is Hope
30. Paragraph The Name of the Title Is Hope
31. Paragraph The Name of the Title Is Hope
32. Paragraph The Name of the Title Is Hope
33. Paragraph The Name of the Title Is Hope
34. Paragraph The Name of the Title Is Hope
35. Paragraph The Name of the Title Is Hope
36. Paragraph The Name of the Title Is Hope
37. Paragraph The Name of the Title Is Hope
38. Paragraph The Name of the Title Is Hope
39. Paragraph The Name of the Title Is Hope
40. Paragraph The Name of the Title Is Hope
41. Paragraph The Name of the Title Is Hope
42. Paragraph The Name of the Title Is Hope
43. Paragraph The Name of the Title Is Hope
44. Paragraph The Name of the Title Is Hope
45. Paragraph The Name of the Title Is Hope
46. Paragraph The Name of the Title Is Hope
47. Paragraph The Name of the Title Is Hope
48. Paragraph The Name of the Title Is Hope
49. Paragraph The Name of the Title Is Hope
50. Paragraph The Name of the Title Is Hope
51. Paragraph The Name of the Title Is Hope
52. Paragraph The Name of the Title Is Hope
53. Paragraph The Name of the Title Is Hope
54. Paragraph The Name of the Title Is Hope
55. Paragraph The Name of the Title Is Hope
56. Paragraph The Name of the Title Is Hope
57. Paragraph The Name of the Title Is Hope
58. Paragraph The Name of the Title Is Hope
59. Paragraph The Name of the Title Is Hope
60. Paragraph The Name of the Title Is Hope
61. Paragraph The Name of the Title Is Hope
62. Paragraph The Name of the Title Is Hope
63. Paragraph The Name of the Title Is Hope
64. Paragraph The Name of the Title Is Hope
65. Paragraph The Name of the Title Is Hope
66. Paragraph The Name of the Title Is Hope
67. Paragraph The Name of the Title Is Hope
68. Paragraph The Name of the Title Is Hope
69. Paragraph The Name of the Title Is Hope
70. Paragraph The Name of the Title Is Hope
71. Paragraph The Name of the Title Is Hope
72. Paragraph The Name of the Title Is Hope
73. Paragraph The Name of the Title Is Hope
74. Paragraph The Name of the Title Is Hope
75. Paragraph The Name of the Title Is Hope
76. Paragraph The Name of the Title Is Hope
77. Paragraph The Name of the Title Is Hope
78. Paragraph The Name of the Title Is Hope
79. Paragraph The Name of the Title Is Hope
80. Paragraph The Name of the Title Is Hope
81. Paragraph The Name of the Title Is Hope
82. Paragraph The Name of the Title Is Hope
83. Paragraph The Name of the Title Is Hope
84. Paragraph The Name of the Title Is Hope
85. Paragraph The Name of the Title Is Hope
86. Paragraph The Name of the Title Is Hope
87. Paragraph The Name of the Title Is Hope
88. Paragraph The Name of the Title Is Hope
89. Paragraph The Name of the Title Is Hope
90. Paragraph The Name of the Title Is Hope
91. Paragraph The Name of the Title Is Hope
92. Paragraph The Name of the Title Is Hope
93. Paragraph The Name of the Title Is Hope
94. Paragraph The Name of the Title Is Hope
95. Paragraph The Name of the Title Is Hope
96. Paragraph The Name of the Title Is Hope
97. Paragraph The Name of the Title Is Hope
98. Paragraph The Name of the Title Is Hope
99. Paragraph The Name of the Title Is Hope
</details>

Figure 2: Screenshot of Step 2 (reading order) in PAVE 2.0.

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 5

heading level skips, such as an <H3> heading directly following an <H1> heading, are corrected by leveling up <H3> to <H2>. In the color-coded bounding boxes the heading levels are indicated at the top right corner to simplify their validation.

### 3.4 Step 4 - Tables

In the fourth step, the user defines the structure of each table in the document. In recent years, automatic table recognition has become popular, but errors still occur [18]. Therefore, explicit user interaction is still necessary to correct tables. However, various table annotating methods have been developed to create new datasets for training deep learning models. One of the most promising is the PDF Table Annotation tool [15]. Inspired by their findings, we developed a table annotating method for this process step which can handle at least simple tables. Due to limitations of our back end and to first focus on the new remediation concept, tables with merged cells or tables that span multiple pages are to be addressed in future work.

The user defines the table structure in PAVE 2.0 by drawing or deleting horizontal and vertical lines in the page view to separate rows and columns (see Figure 3). The tagged table cells are displayed in the workspace pane for reference. The user can also specify whether the first row, first column, or both are header cells. If users upload a PDF with an invalid table tag structure, the table tag structure is automatically updated to meet the UA standard.

### 3.5 Step 5 - Lists

In the fifth step, users define the structure of all lists in the document. The list interface screen is analogous to the table interface screen for consistency. To separate the list items, the user can again draw (horizontal) lines in the page view, and the list is shown on the left side in the workspace pane. The drop-down menu there can be used to create a nested list (a list within a list). As in the previous steps, the user can only create a valid list structure. Furthermore, existing invalid list structures are updated to be valid structures. For the same reasons as in the table step, defining a list spanning multiple pages is to be addressed in future work.

### 3.6 Step 6 - Figures

In the sixth step, users can modify the alternative texts for all figures within the document. To encourage brevity a word counter is integrated into the alternative text editor, adhering to recommendations for shorter alt texts [46]. Nonetheless, research by Williams et al. [48] indicates that longer alt texts are often of higher quality. To balance these findings with the complexity of scientific graphics, we added a word counter which counts down from 50 words, which typically equates to two to four sentences. Nevertheless, users can still add longer alt texts if needed (the word counter will get negative and red). Additionally, users have the option to mark a figure as decorative.

### 3.7 Step 7 - Mathematical Formulas

In step seven, users can modify the alternative texts for all mathematical formulas in the document. Alternative texts for mathematical formulas must adhere to specific rules to prevent ambiguity, which makes it challenging to write valid alternative text, even for experts [12]. We therefore developed a math editor (Figure 4) which allows users to create valid alternative texts for formulas without knowledge of alternative text rules for formulas such as MathSpeak [38].

After opening the math editor, an AI model based on the work of Schmitt-Koopmann et al. [37] predicts the corresponding LaTeX code. We used the same architecture and training process, but adapted the preprocessing pipeline for PDFs. The PDF is converted into a PNG image with a resolution of 600 DPI by using the pdf2image library [4]. The PDF rendering information is used to determine the position of the formula in the PDF file so that it can be cut out of the image. The AI model uses a Convolutional vision Transformer [50] with 3 layers as Encoder and a Decoder Transformer with 8 heads and 4 layers as decoder. The model reaches an Edit score of 97.2% on the im2latexv2 test dataset [35], indicating an average error rate of 3 symbols per 100 symbols in an equation.

The original image of the formula in the PDF is shown in the top left subpane in the workspace pane. The LaTeX code generated by the AI model is displayed in the top right subpane. At the bottom, an interactive editor renders the LaTeX code. Users can correct the formula recognized by the AI model in two ways. First, they can modify the LaTeX code directly in the code pane. Alternatively, users unfamiliar with LaTeX can use the interactive formula editor with the mathematical keyboard at the bottom. As soon as the user has corrected the formula the math editor automatically converts the LaTeX code into an alternative text following the MathSpeak rules.

### 3.8 Step 8 - Meta Information and Page Review

In the last step, users can review each page of the document with an overlay of the added structure (refer to Figure 5). They can also modify the metadata information including title, author, and language. All other meta information required for the UA standard is set automatically.

## 4 User Study Design

### 4.1 Study Goal

We aimed to answer two primary questions with this study. Firstly, how do users feel about the experience of using the guided semi-automatic PAVE 2.0 process, the interface design, ease of navigation, and overall usability of PAVE 2.0 tool? Secondly, how does the quality of tags and processing time with PAVE 2.0 compare to the most commonly used tool, Adobe Acrobat Pro?

### 4.2 Participant Recruitment

Most people are unfamiliar with PDF remediation, so we decided to conduct our study online to reach a broad audience. Furthermore, as our tool is designed for scientific documents, we specifically targeted individuals with a scientific and academic background.

The study by Pradhan et al. [33] inspired our recruitment strategy. Following their idea to maximise participant recruitment, we required only that participants be aware of PDF accessibility.

![](images/fc4fc29aadc77ffe43171f580a9a5152e5f7489391139a3aac5a0ccbe46af4f4.jpg)

<details>
<summary>text_image</summary>

Step 4: Define Table Structure
In this step, you can define the table structure for all tables in your document. The table below illustrates the assigned table structure of the current table. You can draw lines on the page view to separate rows and columns or select them to delete them. Additionally, define whether the first row and/or first column of the table contains a header.
Possible Actions
Split Row/Column: Select Split Row/Column and draw a line in the page view to split a row/column into two rows/columns.
Combine Rows/Columns: Select a line in the page view and select Combine Rows/Columns to delete the line and combine the two rows/columns.
Delete All Table Cells: Remove all rows and columns.
Hints
Highlight Cell: Hover over a cell in the table below to highlight it in the page view.
Next Step
Tables
Split Row/Column
Combine Rows/Columns
Delete All Table Cells
Table 1/1
First row contains headers for the table columns
First columns contains headers for the table rows
A
B
C
1
Command
A Number
Comments
2
author
100
Author
3
table
300
For tables
4
\table*
400
For wider tables
Page 2
Frequently-used parameters, or combinations of parameters, include:
• anonymous, reviews Suitable for a 'double-anonymous' uniform submission. As they present, we have been manually adjusted to the right side of the work.
• author-version Producers a version of the work suitable for posting by the author.
• Screen Producers colored hyperlinks.
This document uses the following string as the first command in the source file:
3 MODIFICATIONS
Modifying the template - including but not limited to adjusting margins, typeface issues, line spacing, paragraph and list definitions and the use of the vapor content to manually adjust the vertical spacing between elements of your work - is not allowed.
Your document will be returned to you for revision if modifications are discovered.
4 TYPEFACES
The "super" Document class requires the use of the "Libertine" typeface family. Your Tik installation should include this set of packages. Please do not substitute other typesface. The "internet" and "Times" packages should not be used, as they will override the built-in typeface families.
5 TITLE INFORMATION
The title of your work should use capital letters appropriately - capitalismlytitle has useful rules for capitalization. Use the 11th command to define the title of your work. If you must have a cuttle define it with the subtitle command. Do not insert line breaks in your title.
If your title is lengthy, you must define a short version to be used in the page headers, to prevent overlapping text. The title commands has a short title" parameter.
6 AUTHORS AND AFFILIATIONS
Each author must be defined separately for accurate metadata identification. As an exception, multiple authors may share one affiliation. Authors' names should not be abbreviated, use full first name when ever possible. Include authors' e-mail addresses whenever possible. Grouping authors' names or e-mail addresses, or providing an "e-mail alias," as shown below, is acceptable.
The author(s) and author/term's commands allow a note to apply to multiple authors - for example, if the first two authors of an article contributed equally to the work.
If your author list is lengthy, you must define a shortened version of the list of authors to be used in the page headers, to prevent overlapping text. The following command should be placed just after the last author(2). Ossisting this command will force the use of a concentrated list of all of the authors' names, which may result in overlapping text in the page headers.
ACM Toma Graph, Vol. 37, No. 8, Article 111. Publication date: August 2018.
1112 • Transacted at:
Frequently-used parameters, or combinations of parameters, include:
• anonymous, reviews Suitable for a 'double-anonymous' uniform submission. As they present, we have been manually adjusted to the right side of the work.
• author-version Producers a version of the work suitable for posting by the author.
• Screen Producers colored hyperlinks.
This document uses the following string as the first command in the source file:
3 MODIFICATIONS
Modifying the template - including but not limitedto adjusting margins, typeface issues, line spacing, paragraph and list definitions and the use of the vapor content to manually adjust the vertical spacing between elements of your work - is not allowed.
Your document will be returned to you for revision if modifications are discovered.
4 TYPEFACES
The "super" Document class requires the use of the "Libertine" typeface family. Your Tik installation should include this set of packages. Please do not substitute other typesface. The "internet" and “Times" packages should not be used, as they will override the built-in typeface families.
5 TITLE INFORMATION
The title of your work should use capital letters appropriately - capitalismlytitle has useful rules for capitalization. Use the 11th command to define the title of your work. If you must have a cuttle define it with the subtitle command. Do not insert line breaks in your title.
If your title is lengthy, you must define a short version to be used in the paper headers, to prevent overlapping text. The title commands has a short title" parameter.
6 AUTHORS AND AFFILIATIONS
Each author must be defined separately for accurate metadata identification. As an exception, multiple authors may share one affiliation. Authors' names should not be abbreviated, use full first name when ever possible. Include authors' e-mail addresses whenever possible. Grouping authors' names or e-mail addresses, or providing an "e-mail alias," as shown below, is acceptable.
The author(s), and author/term's commands allow a note to apply to multiple authors - for example, if the first two authors of an article contributed equally to the work.
If your author list is lengthy, you must define a shortened version of the list of authors to be used in the page headers, to prevent overlapping text. The following command should be placed just after the last author(2). Ossisting this command will force the use of a concentrated list of all of the authors' names, which May result in overlapping text in the page headers.
ACM Toma Graph, Vol. 37, No. 8, Article 111. Publication date: August 2018.
7 RIGHTS INFORMATION
Authors of any work published by ACM will need to complete a rights form. Depending on the kind of work, and the rights management choice made by the author, this may be copyright transfer, permission, license, or an OA (open access) agreement.
Regardless of the rights management choice, the author will receive a copy of the completed rights form once has been submitted. This form contains EPGI commands that must be copied into the source document. When the document source is compiled, these commands and their parameters add formatted text to several areas of the final document:
• the ACM Reference Format" text on the first page.
• the "rights management" text on the first page.
• the conference information in the page header(s).
Rights information is unique to the work; if you are reporting several works for an event, make sure to use the correct set of commands with each of the works.
The ACM Reference Format text is required for all articles over one page in length, and is optional for one-page articles (abstracts).
8 CCS CONCEPTS AND USER-DEFINED KEYWORDS
Two elements of the "super" document class provide powerful taxonomic tools for you to help readers from your work on an online search.
The ACM Computing Classification System is a set of classifiers and concepts that describe the computing discipline. Authors can select entries from this classification system, via acn, and generate the commands to be included in the EPGI source.
User-defined keywords are a comma-separated list of words and phrases of the authors' choosing, providing a more flexible way of describing the research being presented.
CCS concepts and user-defined keywords are required for all articles over two pages in length, and are optional for one- and two-page articles (or abstracts).
9 SECTIONING COMMANDS
You work should use standard EPGI sectioning commands section,
subsection, subsection section, and paragraph. They should be numbered,
do not remove the numbering from the commands.
</details>

Figure 3: Screenshot of Step 4 (tables) in PAVE 2.0.

![](images/4ec73486ccffe84ad7a24e95a6759d4da906418857e9a22833ea986e5dd94b30.jpg)

<details>
<summary>text_image</summary>

Math Editor
With the math editor, you can generate an alternative text from LaTeX code. Wait that the AI model recognized the formula. Then check and edit the formula. The top left view shows you the original image. The top right view the current LaTeX code, which you can edit. The bottom view is an interactive editor that render the LaTeX
code and allows the modification by writing in the editor and using the mathematical keyboard. The alternative text can then be generated automatically.
Possible Actions
Generate Alternative Text: Generating the alternative text from the LaTeX code.
Original Mathematical Formula
LaTeX Code
|sum_i = 0|^ {infty} x_i = int_(0)^(pi + 2) f
∑_{i=0}^∞ x_i = ∫_0^π+2 f
Interactive Editor
∑_{i=0}^∞ x_i = ∫_0^π+2 f
Mathematical Expression	Operators	Symbols
x^*	x_n	·	_x	x_z	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x	¯x
search...
Generate Alternative Text
</details>

Figure 4: Screenshot of the math editor. The top left box shows the original formula from the PDF. The top right box shows the LaTeX code. At the bottom is the interactive editor with a mathematical keyboard.

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy

![](images/ee9e2f52edd99674b50c56d7335c7eb0e2c7c37d3fa695fe9e63bf981195e026.jpg)

<details>
<summary>text_image</summary>

Step 8: Check Meta Information and Final Results
In this step, you can refine the meta information of the PDF. An accessible PDF requires a title, author, and a language. In the page view, you can see the tags.
Please check them and if needed, go to the previous steps to refine them.
Pages
1 / 3
(2 Pages not checked)
Title (required):
The Name of the Title Is Hope
Author (required):
ACM
Language (required):
English *
Keywords:
Subject:
Download file
Page 1
[1] H1
[2] Paragraph
EN TROVATO, Institute for Clarity in Documentation, USA
LARS TH RVALD, The Thervald Group, Iceland
VALERIE BÉRANGER, Inria Paris-Récquencourt, France
PARNA PATEL, Rajiv Gandhi University, India
RAUEN CHAN, Tinghua University, China
CHARLES PALMER, Palmer Research Laboratories, USA
JOHN SMITH, The Thervald Group, Iceland
WILUS P. KUMOLAT, Thailand
[3] Paragraph
What and without documentation is important to provide our best information for publication by ACM in accordance with the present of publication. Based on the "reason" document class, this article presents an update many of the common versions, as well as many of the formering features as further we are in the original data collection table.
[4] Paragraph
U. Cucopie - Do Not Use This Code - Calendar New Chinese Press in Your Paper: Generates the Current Image for the New York Times. The New York Times will be updated in the following: 
[5] Paragraph
[6] Paragraph
[7] Paragraph
A.M. recommended article templates have been customized, and their unique features incorporated into this single new template.
If you are now to publishing with ACM, this document is valid to guide to the process of preparing a case with the publication.
[8] H2
[9] Paragraph
A.M. recommended article templates have been customized, and their unique features incorporated into this single new template.
If you are now to publishing with ACM, this document is valid to guide to the process of preparing a case with the publication.
[10] Paragraph
[11] Paragraph
[12] H2
[13] Paragraph
a detailed in the introduction, which is a key feature that is used to prepare many different kinds of documentation - a double-undersensitive initial submission of a full-length technical paper, two-page SIGGRAPH Emerging Technologies abstract, a "current model" journal article, a SIGCM Extended Abstract, and more - all by selecting the appropriate item. Late style and two fair presented. This document will explain the unique features of the document list. For further information, the FIGM User's Guide is available.
[14] H3
[15] Paragraph
The primary parameter given these papers, which corresponds to the same style which corresponds to the kind of publication or the publishing the work. This parameter is enclosed in square brackets and is part of the documents command. Journals use one or more template styles. All but there ACM consists on the approximate template.
[16] List
[17] Paragraph
[18] List
[19] List
[20] Paragraph
[21] Paragraph
and/or specifying the text in each section of the course has been written out of some other forms. It is a number of five fair elements which could have some part of the applied template style. A complete list of these parameters can be found in the JPM User's Guide.
Artifact
</details>

Figure 5: Screenshot of Step 8 (meta information) in PAVE 2.0.

To achieve a similar balance between novice and experienced participants, we aimed to recruit a study population in which half of the participants had remediated fewer than 10 PDFs (novice users) and the other half had remediated at least 10 PDFs (experienced users). We distributed the study invitation to relevant online communities, such as the WHO GATE community, and within our social and professional networks.

We recruited 19 participants for our study. One of the participants was aged between 18 and 30, nine were aged between 31 and 40, six were aged between 41 and 50, and three were aged between 51 and 60. Thirteen participants identified as female, four as male, one as non-binary, and one did not disclose their gender. Eleven participants were located in Switzerland, five were in Austria, one was in Germany, and two were in Spain.

### 4.3 Study Procedure

We compared the efficiency and effectiveness of our novel process and tool with the de facto standard PDF remediation tool Adobe Acrobat Pro. The study was conducted online via MS Teams or ZOOM depending on participants’ preferences. We recorded the screen and audio to analyze the interactions and transcribe the interviews.

The study was separated into four parts. In the first part of the study, we welcomed the participants, and collected demographic information and information about their previous PDF remediation experience. In Parts 2 and 3, the participants were asked to complete a remediation task with each of the two PDF remediation tools (one tool in Part 2 and the other tool in Part 3). To mitigate bias and learning effects, we counterbalanced the order of the tools. After each task, we conducted a semi-structured interview to gather insights into their experiences with the tool. The task is described in Section 4.4. Part 4 consisted of a structured interview with closed-ended questions. In this part, the participants were asked to compare the two tools through questions like "Which tool do you prefer to use in the future?" and "Which of the tools makes your work faster and more efficient?".

### 4.4 Task Design

After setting up and trying out the tool, participants were asked to remediate a scientific PDF without tags. To keep the task duration manageable the PDF was a shortened 3-page version of the ACM LaTeX template with a two-column structure. The final PDF contained seventeen headings, four lists, one figure, one table, and three mathematical formulas. We created two slightly different versions of the PDFs and counterbalanced them to ensure that the order of the PDF versions did not affect the results. For the sake of ecological validity, we wanted the task to reflect real world use of PDF remediation tools, so we allowed the participants to use any additional support they wanted, such as Google.

We decided against creating detailed tutorials for each tool and provided only a brief introduction to each tool as we were also interested in whether the tools were self-explanatory and easily learnable without explicit instruction. For Adobe Acrobat Pro, we helped participants find the accessibility tools and showed them how the accessibility report works. Additionally, we showed them the help page for Adobe Acrobat’s accessibility tools. For PAVE 2.0, we explained that the tool is split into eight steps, and that they could always find a description of each step in the top left corner. To gain some initial familiarity with each tool, they were allowed to try it out for up to 5 minutes with a sample PDF, similar to the user study by Pradhan et al. To limit the duration of the study, we set a time limit of 20 minutes. If the participants were stuck for more than 3 minutes, we helped them so they could continue.

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 8

### 4.5 Data Analysis

After obtaining approval from our organization’s ethical committee, we conducted the user study via MS Teams or ZOOM. The first author conducted all the interviews. During the user study, we recorded participants’ audio and screens. The interviews were transcribed automatically with MS Teams/OneDrive and manually corrected to ensure a high-quality transcript. The interviews were analyzed using deductive and inductive coding. Prior to the analysis, an initial coding scheme was developed based on our research questions and the interview guide. Following Saldaña’s method [34], a researcher who was not the interviewer assigned codes to relevant content during the first cycle of analysis. In a second cycle, codes were combined to form more abstract categories. The interviewer and the researcher who had assigned the initial codes executed the second cycle together.

In addition to collecting qualitative feedback we used two quantitative metrics. First, we analyzed the screen recordings and determined the time per step in PAVE 2.0. The time duration was summed up if the participants jumped forth and back between steps. Since Adobe Acrobat has no clear workflow, we could not split the time up into steps. Second, we assessed the accessibility of the remediated PDFs created by the participants by analyzing the structure tree with Adobe Acrobat Pro and our previously defined tag accuracy criteria defined in section 4.6. The analysis of the tag accuracy was done by the interviewer for all PDFs.

### 4.6 Tag Accuracy Criteria

The PDF accessibility analyses presented in Section 2 evaluate the accessibility of a PDF based mainly on metadata and machine-checkable criteria. However, these methods do not reveal other concerns, for example whether all headings are correctly tagged [19]. Therefore, we defined thirteen manually checkable criteria to evaluate the tag accuracy of a tagged PDF using the Matterhorn Protocol [30], the best-practice guide of the PDF Association [31], and the synthetic errors defined by Pradhan et al. For each criterion we used the following score:

\[
score = \frac {C T}{C T + W T} \cdot 100 \%
\]

Correct Tag (CT) refers to the number of elements tagged accurately. Wrong Tag (WT) indicates the number of elements that should have been tagged but were not tagged, were tagged incorrectly, or should not have been tagged but were tagged. We determined the number of CTs and WTs by analyzing manually the structure tree with Adobe Acrobat Pro. We would like to emphasize that evaluating these criteria requires much experience with tagged PDFs and is only recommended for PDF accessibility experts. The criteria we used are as follows:

• All Content Tagged: Checks if all elements in a PDF are tagged (Matterhorn checkpoint 01-005).   
• Reading Order: Checks if a page is completely tagged and the reading order is not disrupted (Matterhorn checkpoint 09-001). For example, a figure appearing in a sentence is counted as an error. However, if a figure appears after Paragraph 1 instead of Paragraph 2 this is not counted as an error.

• Headings Tagged: Checks if the heading is tagged as a heading, independent of the level (Matterhorn checkpoint 14-001). Since the document title can be tagged as a paragraph or an H1, we counted both as a correct heading.   
• Headings Tagged + Level: Checks if the Headings Tagged criterion is fulfilled and if the heading has the correct heading level (Matterhorn checkpoints 14-002, 14-003, 14-004, and 14-005). Similar to the criteria Headings Tagged, the document title could be tagged as a paragraph or a level 1 heading. However, depending on the title tag, the levels of the other headings must be adjusted.   
• Tables Tagged: Checks if all PDF elements that are part of a table are in the table tag (Matterhorn checkpoints 15-005).   
• Tables Tagged + Structure: Checks if the Tables Tagged criterion is met and if the table structure (<TR>, <TH>, <TD>) is correct (Matterhorn checkpoints 09- 002, 09-004, 15-001, and 15-002).   
• Lists Tagged: Checks if all PDF elements part of a list are in the list tag (Matterhorn checkpoint 17-001). The focus is on elements that visually appear as lists. For example, a collection of bullet points or numbered items should be tagged as a list. Conversely, elements that are not visually presented as lists, such as authors of a paper, are not required to be tagged as lists. If such elements are tagged as a list, they will not be counted as errors.   
• Lists Tagged + Structure: Checks if the Lists Tagged criterion is fulfilled and if the list items are separated correctly with <LI> tags (Matterhorn checkpoints 09- 002 and 09-005).   
• Figures Tagged: Checks if all PDF elements that are part of a figure are in the figure tag (Matterhorn checkpoints 13-001 and 13-006). If the caption tag was included in the figure, it was not counted as an error.   
• Figures Tagged + Alt Text: Checks if the Figures Tagged criterion is fulfilled and if an alternative text was set (Matterhorn checkpoints 13-004 and 13-005). The quality of the alternative text is not evaluated.   
• Formulas Tagged: Checks if all PDF elements that are part of an isolated formula are in the formula tag (Matterhorn checkpoint 17-001). We do not count it as an error if the formula reference was part or not of the formula tag. Formulas embedded in the text are not checked, as the distinction between embedded formulas in the text and standard text requires a detailed analysis of the text. Furthermore, it is unclear whether single symbols like  should be tagged as formulas with alternative text.   
• Formulas Tagged + Alt Text: Checks if the Formulas Tagged criterion is fulfilled and if an alternative text was set (Matterhorn checkpoint 17-002). The quality of the alternative text is not evaluated.   
• Captions: Checks if all PDF elements that are part of a figure caption or table caption are in the caption tag (Matterhorn checkpoint 13-003).

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 9

## 5 Results

We asked participants how often they make PDFs accessible: six novice participants had never done it before, and one novice participant had attempted it only once. One novice participant reported remediating PDFs approximately once a year, three experienced participants stated they did it a few times a year, one novice and four experienced participants did it approximately once a month, and one novice and two experienced participants approximately once a week.

Participants had knowledge of various tools for making PDFs accessible. The most frequently mentioned was Adobe Acrobat Pro’s accessibility tools (16 participants). Participants were also aware of PAVE (8 participants) and Microsoft Office’s accessibility export tools (7 participants). A minority mentioned other tools, such as Axes4 or PAC. They had used these tools to make various documents accessible, including reports, presentations, and educational materials such as exercises and handouts.

In section 5.1 we present the tag accuracy scores, data regarding time spent, and quantitative feedback. Section 5.2 summarizes the qualitative feedback on PAVE 2.0. Section 5.3 summarizes the qualitative feedback on Adobe Acrobat Pro.

### 5.1 Quantitative Results

#### 5.1.1 Tag Accuracy Results

To evaluate the tag accuracy in the remediated PDFs, we used the criteria defined in Section 4.6. Table 1 shows that on average experienced users remediated the PDFs 90.7% better with PAVE 2.0 than with Adobe Acrobat Pro for all categories. Novice users remediated the PDFs 91.8% better on average with PAVE 2.0 for all categories except the reading order. However, the difference between experienced and novice users is relatively small for both tools, averaging a 4.9 pp. difference with PAVE 2.0 and an average difference of 2.8 pp. with Adobe Acrobat Pro. Interestingly, similar to the findings of Pradhan et al., novice users could correct the reading order better than experienced users with Adobe Acrobat Pro. The low "All Content Tagged" score of experienced users with Adobe Acrobat Pro (44.4%) shows that only 4 of 9 PDFs were completely tagged. This indicates that the majority of the experienced users could not finish the tagging process in time. The reasons are that experienced users tagged the PDF manually or deleted larger parts of the automatically created tags.

To determine the influence of each tool’s automatic tagging function, Table 1 also includes their respective auto-tagging scores. We want to emphasize that these auto-tagging scores depend heavily on the characteristics of the PDF itself. Hence, we want to share our anecdotal experience and insights with the autotagging functionalities of PAVE 2.0 and Adobe Acrobat Pro to provide a comprehensive overview. We observed that the autodetecting of the regions in PAVE 2.0 works reliably for scientific documents, such as conference papers, but shows weaknesses with non-scientific documents. Due to the limitation of classes in the training dataset, it cannot detect captions, footnotes, and other infrequently used content types, and typically tags them as paragraphs. Due to the recognition of heading levels based on the font information, heading levels that use the same font (size and style) are not recognized correctly. The mathematical formula recognition works reliably for single-line mathematical expressions but shows weaknesses for single mathematical symbols or multi-line mathematical expressions. Adobe Acrobat Pro’s auto-tagging function often fails to detect inline headings and the correct heading level. Additionally, mathematical formulas and captions are often not tagged correctly. While the list structure is usually detected very well, the list tag sometimes does not contain the complete list. Similarly, if tables are recognized correctly, the table structure is recognized often very well.

The auto-tagging results show that PAVE 2.0’s auto-tagging reaches an average score of 56.9%, 19.4 pp. higher than Adobe Acrobat Pro. Additionally, our results showed that experienced and novice users could improve the auto-tagging results by 23.2 pp. and 18.3 pp. respectively through manual correction using PAVE 2.0. In contrast, experienced and novice users could only improve the auto-tagging results by 4.5 pp. and 1.7 pp. when using Adobe Acrobat Pro.

Furthermore, the results show that users could improve the tag accuracy of the auto-tagging with PAVE 2.0 for all criteria, except for the Figures Tagged and Formulas Tagged + Alt Text criteria. The Figures Tagged score is lower because some users erroneously marked the figure as an artifact. The lower score for Formulas Tagged + Alt Text criteria occurred because several users did not reach Step 7 before time ran out. The scores for participants who reached Step 7 were 87.5% for novice users and 100% for experienced users. Interestingly, the caption scores for PDFs remediated by both tools are very low. These low caption scores can be explained by the fact that both Adobe Acrobat Pro and PAVE 2.0 automatically tag the captions as paragraphs. Hence, if the user is unfamiliar with the caption tag, the caption will remain a paragraph.

The reading order scores with PAVE 2.0 for PDFs from experienced and novice users are surprisingly low. The main reason for this is the typical structure of the first page of the PDF. Most participants defined the reading order from the top to the bottom, with the left column first and the right column second. However, this resulted in the ACM reference format in the bottom left corner of the first page being incorrectly read in the middle of the normal text paragraph (see Figure 2). Hence, the first page was incorrect in 15 of 19 PDFs remediated with PAVE 2.0, accounting for 78% of errors among experienced users and 38% of errors among novice users. In contrast, using Adobe Acrobat Pro, the first page had an incorrect reading order in 17 out of 19 PDFs, representing 25% of experienced users’ errors and 80% of novice users’ errors. This corresponds to our observation that most participants did not review or correct the automatically generated reading order.

To compare the tag accuracy scores reached in our study with current scientific papers, we calculated the tag accuracy scores of the existing tags for 10 papers from each of three popular accessibility research conferences (ASSETS 2023 [3], CHI 2024 [25], ICCHP 2024 [24]). The papers were selected randomly with the help of a number generator, while the order of the papers in the proceedings determined the paper number. For ASSETS and ICCHP all 10 papers were tagged. For CHI 8 of 10 papers were tagged, as a result, we calculated the scores based on the 8 tagged PDFs. The CHI papers had on average the most pages with 14.25 without references and appendix (ASSETS: 12.2, ICCHP: 8.3). CHI papers also contained most headings per page

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 10

with 3.16 (ASSETS: 3.11, ICCHP: 2.08). Figures are the most popular component of the four components (tables, lists, figures, and formulas) for all conferences (CHI: 0.61 figures per page, ICCHP: 0.52, and ASSETS: 0.4). Formulas instead are the least popular component (CHI: 0.11 formulas per page, ICCHP: 0.04, and ASSETS: 0.01). Interestingly, ASSETS papers contained more lists per page (0.21) than CHI papers (0.17) and ICCHP papers (0.10), while for the other component types CHI papers contained the most components per page. The component counts in our sample differ slightly from those reported by Menzies et al. [22] for 330 ASSETS papers between 2011 and 2020. On average, they observed 2.0 tables per paper (1.7 in our sample), 9.2 figures per paper (5.0 in our sample), and 0.3 formulas per paper (0.1 in our sample).

We observed that the tag accuracy and tagging strategy vary greatly from paper to paper for all conferences. For instance, some papers tagged inline headings (level 3 in the ACM template) as headings, while others tagged them as paragraph. We also observed that in some papers, the caption tag is nested within the figure tag, and in others, it appears after the figure tag. This inconsistent tagging strategy indicates that the papers were tagged with different (interpretations) or no guidance. The average score indicates that the conference papers are slightly more accessible compared to the results with Adobe Acrobat Pro, but clearly lower than with PAVE 2.0. We observed that ASSETS and CHI papers never tagged the "Check for updates" button (figure with a link), while it was tagged in 7 of 10 of the ICCHP PDFs. Failing to tag the "Check for updates" button is also the reason for the 0 scores in the criteria "All Content Tagged" for the ASSETS and CHI papers. Furthermore, the evaluation shows the great value ASSETS and CHI put on tagging figures with alt text, while the ICCHP papers never included alternative text. A reason for the high reading order score of the ICCHP PDFs could be the simpler one-column layout, compared to the two-column layout of ASSETS and CHI.

#### 5.1.2 Time Performance

Table 2 shows the average time novice and experienced participants spent using each tool, as well as the number of participants who reached each step and the number of instructions required with PAVE 2.0. We have included the timing reported by Pradhan et al. for the Ally tool, but it is important to note that the task they performed involved correcting errors in PDFs that were already tagged, which is a different task than tagging an untagged PDF.

Interestingly, novice users were faster and needed fewer instructions than experienced users with PAVE 2.0. Both novice and experienced users spent most of their time on the first two steps of PAVE 2.0. Novice users were quicker with PAVE 2.0, while experienced users spent more time with PAVE 2.0 than with Adobe Acrobat Pro. Out of the 19 participants, five finished before the 20-minute time limit with Adobe Acrobat Pro. However, all five participants mentioned that the PDF was probably not completely accessible, but they did not know how to fix the remaining issues. One participant had to give up because Adobe Acrobat Pro stopped working multiple times. Novice users spent 13 minutes and 21 seconds for the first four steps, which is similar to previous findings regarding the four subtasks of the Ally prototype (the Ally prototype only has these four subtasks in its remediation process). However, experienced users spent 15 minutes and 3 seconds for the first four steps, which is around 2 minutes longer than with the Ally tool.

![](images/637ecc9555e09ca301181db8fb2d7a26fa750eb138ce727769a6242900d8c094.jpg)

<details>
<summary>bar_stacked</summary>

Acceptable Time Spending Per Page
| Category | up to 1 min (%) | 2 to 5 min (%) | 6 to 10 min (%) | 11 to 20 min (%) | more than 21 min (%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| exper. | 22 | 34 | 23 | 10 | 8 |
| novice | 20 | 37 | 23 | 9 | 0 |
</details>

Figure 6: Answers of experienced and novice participants, about how much time they would be willing to spend per page to make a PDF accessible.

The timings further reveal that optimizing steps 1 and 2 with better AI models or improved user interfaces holds the greatest potential for accelerating the remediation process. Nevertheless, automating the other steps can influence the PDF remediation speed similarly depending on the used documents. For example, figures in CHI papers are very frequent (see Table 1). Hence, we believe an improved figure step with specialized AI models for scientific graphics and images could reduce the burden of the PDF remediation process of CHI papers significantly.

We asked participants how much time they would be willing to spend per page to remediate a PDF and categorized the responses into five ranges. As shown in Figure 6, around 80% of the novice and experienced users stated that 2 to 5 minutes per page would be acceptable. Novice users spent on average 5 minutes and 48 seconds per page, while experienced users spent 6 minutes and 35 seconds in our study with PAVE 2.0. This means that about 40% of participant would already have fallen into the desired 2-5 minutes per page range in upon their first use of PAVE 2.0.

#### 5.1.3 Quantitative Feedback

We asked participants to compare PAVE 2.0 and Adobe Acrobat across various aspects through four specific questions (see Figure 7). When asked which tool they would prefer to use in the future, fifteen participants indicated a preference for PAVE 2.0. Two participants stated their preference would depend on the specific PDF, alternating between Adobe Acrobat Pro and PAVE 2.0. The last two participants stated they would prefer to use Adobe Acrobat Pro in the future. One of them expressed uncertainty about PAVE 2.0’s ability to handle large PDFs, and the other desired an offline tool, which is simpler compared to Adobe Acrobat Pro.

Regarding ease of use, eighteen participants found PAVE 2.0 simpler, while one participant preferred the usability of Adobe Acrobat Pro. Sixteen participants responded that they believed PAVE 2.0 could enhance their current or future work with accessible PDFs. However, two participants were unsure, citing some limitations of PAVE 2.0, and one person felt that they were more efficient using Adobe Acrobat Pro. Despite these mixed preferences, all participants agreed they would recommend PAVE 2.0 to novice users seeking to make a PDF accessible.

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 11 

<table><tr><td rowspan="2">Criteria</td><td colspan="3">Adobe Acrobat Pro</td><td colspan="3">PAVE 2.0</td><td colspan="3">Conferences</td></tr><tr><td>Exp.[%]</td><td>Novice[%]</td><td>Auto[%]</td><td>Exp.[%]</td><td>Novice[%]</td><td>Auto[%]</td><td>ASSETS[%]</td><td>CHI[%]</td><td>ICCHP[%]</td></tr><tr><td>All Content Tagged</td><td>44.4</td><td>90.0</td><td>100.0</td><td>100.0</td><td>100.0</td><td>100.0</td><td>0.0 (10)</td><td>0.0 (8)</td><td>70.0 (10)</td></tr><tr><td>Reading Order</td><td>37.0</td><td>66.7</td><td>66.7</td><td>66.7</td><td>63.3</td><td>0.0</td><td>59.8 (122)</td><td>56.1 (114)</td><td>91.6 (83)</td></tr><tr><td>Headings Tagged</td><td>83.7</td><td>75.3</td><td>70.6</td><td>100.0</td><td>98.2</td><td>94.1</td><td>71.8 (379)</td><td>72.8 (360)</td><td>47.4 (173)</td></tr><tr><td>+ Level</td><td>76.5</td><td>54.1</td><td>0.0</td><td>79.7</td><td>86.5</td><td>70.6</td><td>71.0 (379)</td><td>72.5 (360)</td><td>42.8 (173)</td></tr><tr><td>Tables Tagged</td><td>33.3</td><td>10.0</td><td>0.0</td><td>100.0</td><td>100.0</td><td>100.0</td><td>66.7 (17)</td><td>73.7 (19)</td><td>43.8 (16)</td></tr><tr><td>+ Structure</td><td>0.0</td><td>10.0</td><td>0.0</td><td>77.8</td><td>70.0</td><td>0.0</td><td>29.4 (17)</td><td>31.6 (19)</td><td>0.0 (16)</td></tr><tr><td>Lists Tagged</td><td>52.8</td><td>60.0</td><td>75.0</td><td>100.0</td><td>92.5</td><td>75.0</td><td>57.7 (26)</td><td>31.6 (19)</td><td>75.0 (8)</td></tr><tr><td>+ Structure</td><td>50.0</td><td>60.0</td><td>75.0</td><td>77.8</td><td>72.5</td><td>0.0</td><td>57.7 (26)</td><td>31.6 (19)</td><td>75.0 (8)</td></tr><tr><td>Figures Tagged</td><td>55.6</td><td>40.0</td><td>100.0</td><td>77.8</td><td>70.0</td><td>100.0</td><td>90.0 (50)</td><td>92.9 (70)</td><td>100.0 (43)</td></tr><tr><td>+ Alt Text</td><td>55.6</td><td>30.0</td><td>0.0</td><td>55.6</td><td>50.0</td><td>0.0</td><td>90.0 (50)</td><td>92.9 (70)</td><td>0.0 (43)</td></tr><tr><td>Formulas Tagged</td><td>37.0</td><td>13.3</td><td>0.0</td><td>100.0</td><td>100.0</td><td>100.0</td><td>0.0 (1)</td><td>61.5 (13)</td><td>0.0 (3)</td></tr><tr><td>+ Alt Text</td><td>14.8</td><td>0.0</td><td>0.0</td><td>77.8</td><td>70.0</td><td>100.0</td><td>0.0 (1)</td><td>0.0 (13)</td><td>0.0 (3)</td></tr><tr><td>Captions Tagged</td><td>5.6</td><td>0.0</td><td>0.0</td><td>27.8</td><td>5.0</td><td>0.0</td><td>3.0 (67)</td><td>10.2 (88)</td><td>61.0 (59)</td></tr><tr><td>Average Score</td><td>42.0</td><td>39.2</td><td>37.5</td><td>80.1</td><td>75.2</td><td>56.9</td><td>45.9</td><td>48.3</td><td>46.7</td></tr></table>

Table 1: Overview of the tag accuracy score of the remediated PDFs by novice, experienced users or only using the auto tagging function. To compare the results, we evaluate ten randomly selected papers of each conference (Assets 2023, CHI 2024, and ICCHP 2024) additionally. The values are percentages of elements fulfilling the criteria. The brackets indicate the total number of elements related to the criteria (CT + WT).

<table><tr><td rowspan="2">Step</td><td colspan="5">Novice Users</td><td colspan="5">Experienced Users</td></tr><tr><td>Time [m:ss]</td><td>Done [n]</td><td>Instr. [n]</td><td>Adobe [m:ss]</td><td>Ally [m:ss]</td><td>Time [m:ss]</td><td>Done [n]</td><td>Instr. [n]</td><td>Adobe [m:ss]</td><td>Ally [m:ss]</td></tr><tr><td>1-Regions</td><td>3:01</td><td>10</td><td>1</td><td>-</td><td>4:31</td><td>6:25</td><td>9</td><td>1</td><td>-</td><td>4:46</td></tr><tr><td>2-Reading Ord.</td><td>6:48</td><td>10</td><td>5</td><td>-</td><td>3:23</td><td>4:36</td><td>9</td><td>4</td><td>-</td><td>4:10</td></tr><tr><td>3-Heading Str.</td><td>1:37</td><td>10</td><td>0</td><td>-</td><td>1:39</td><td>1:23</td><td>8</td><td>1</td><td>-</td><td>1:15</td></tr><tr><td>4-Tables</td><td>1:55</td><td>10</td><td>2</td><td>-</td><td>3:46</td><td>2:39</td><td>8</td><td>3</td><td>-</td><td>3:07</td></tr><tr><td>5-Lists</td><td>1:28</td><td>9</td><td>0</td><td>-</td><td>-</td><td>1:36</td><td>8</td><td>1</td><td>-</td><td>-</td></tr><tr><td>6-Figures</td><td>0:25</td><td>8</td><td>0</td><td>-</td><td>-</td><td>0:52</td><td>7</td><td>0</td><td>-</td><td>-</td></tr><tr><td>7-Formulas</td><td>1:12</td><td>8</td><td>0</td><td>-</td><td>-</td><td>1:33</td><td>7</td><td>1</td><td>-</td><td>-</td></tr><tr><td>8-Meta Inf.</td><td>0:59</td><td>7</td><td>0</td><td>-</td><td>-</td><td>0:39</td><td>6</td><td>0</td><td>-</td><td>-</td></tr><tr><td>total</td><td>17:25</td><td>-</td><td>8</td><td>17:30</td><td>13:16</td><td>19:44</td><td>-</td><td>11</td><td>18:34</td><td>13:18</td></tr></table>

Table 2: Overview of the average time spent by the participants for each step, split by novice and experienced users. Additionally, it shows how many participants have done a step and how many participants required instructions. Additionally, it shows the timings observed with the four steps of the Ally tool.

### 5.2 PAVE 2.0 User Experiences

Most participants started Step 1 with the "Detecting Regions" function and reviewed the results. Three participants mentioned it would be beneficial if the automatic detection of the regions would run without their needing to click on the button (however, this would delete already tagged regions in the PDF). Two participants needed clarification on how to adjust the size of regions or merge them. Additionally, we observed that six participants were uncertain about the appropriate region types. One participant mentioned that they would like to have a selection guide for the region-type selection. For instance, they would appreciate knowing the possible region types for a footer. This issue of being unaware of the possible region types could also explain why fifteen participants did not label any captions as captions. Three participants mentioned that they appreciated the color-coded region types. Nevertheless, only a few participants noticed all region-type errors made by the AI model in this step, e.g., that a heading was labeled as a list. Therefore, fourteen participants had to return to Step 1 to make corrections later on. Two participants mentioned that they would like to have an undo function in this step as well as for later steps.

We observed that defining the reading order (Step 2) was the most time-consuming step. Most of the participants began by changing the reading order via the list, which is the more timeconsuming process. However, around half of the participants discovered the "Draw Reading Order" function on their own. For the remaining nine participants, we had to provide a hint for them to detect the functionality. Nonetheless, after discovering the "Draw Reading Order" function, all participants found it useful. Four participants pointed out, however, that the feature requires some training, and that the detection of the boxes could be improved. Most participants appreciated the visualization of the reading order with a line graph. However, one participant mentioned that the lines and numbers obscured some parts of the text which made the review of the reading order more challenging. Another participant stated that they would appreciate if red and green color combinations were avoided and the overall color contrast was increased, on account of the challenges they present for colorblindness.

![](images/4e5df10439d673e20868adfbe6379a4954aaa0c23324f9e75f4e01684705db09.jpg)

<details>
<summary>bar_stacked</summary>

using in the future
| Category | PAVE 2.0 (%) | Adobe Acrobat Pro (%) | No Answer (%) |
| :--- | :--- | :--- | :--- |
| exper. | 65 | 10 | 18 |
| novice | 88 | 9 | 0 |
The chart displays a horizontal stacked bar for each category, with the legend indicating the three response types.
</details>

(a)

![](images/ee8c15a0c6bbcaf62386f0d2f21c90bcc9c648880ba5c32c79f564432b350315.jpg)

<details>
<summary>bar_stacked</summary>

simpler
| Category | PAVE 2.0 (%) | Adobe Acrobat Pro (%) | No Answer (%) |
| :--- | :--- | :--- | :--- |
| exper. | 98 | 0 | 0 |
| novice | 89 | 13 | 0 |
</details>

![](images/445cecae78dec91d0cf146add1f3cfac7230ea5bcad32db2d9d690d7a6d70715.jpg)

<details>
<summary>bar_stacked</summary>

more efficient
| Category | PAVE 2.0 (%) | Adobe Acrobat Pro (%) | No Answer (%) |
| :--- | :--- | :--- | :--- |
| exper. | 87 | 11 | 0 |
| novice | 79 | 11 | 11 |
</details>

(c)

![](images/d5cf1e3e0b9dc58d51697a95039dc4dc22b71f9c6d4601a083a68be30fc9a630.jpg)

<details>
<summary>bar</summary>

recommended for novice user
| Recommendation | PAVE 2.0 (%) | Adobe Acrobat Pro (%) | No Answer (%) |
| :--- | :--- | :--- | :--- |
| exper. | 100 | 0 | 0 |
| novice | 100 | 0 | 0 |
</details>

Figure 7: Quantitative feedback of novice and experienced users of the following four questions: a) Which tool do you prefer to use in the future? b) Which of the tools is easier to use? c) Which of the tools makes your work faster and more efficient? d) If somebody has no experience with PDF remediation. Which of the tools would you recommend?

Organizing the heading levels (Step 3) was straightforward for most participants. Only two participants used the automatic detection of the heading levels; the other participants did everything manually. Two participants were confused that they could not navigate through the pages with a page navigation bar and had to click on a heading to jump to the correct page. One participant said they would like to create an <H> tag or <Title> tag for the paper’s title.

Step 4 (tables) was the first object-specific step. As with the "Draw Reading Order" function, most participants did not understand how to draw the table at first. Thirteen participants figured out how to do so themselves, while five participants required instruction. Nevertheless, eight participants mentioned that they liked this step and said it was a simple solution for tables. Two participants mentioned the issue of irregular tables and tables on multiple pages, which cannot easily be addressed with this approach. One participant stated they would have preferred if the possible options for columns and rows had been highlighted.

The list remediation step (Step 5) is similar to the one for tables. As a result, participants were already familiar with the drawing functionality and completed this step with four lists much more quickly than the table step with one table. As with the table step, two participants mentioned that having a solution for lists over multiple pages and two-column lists would be beneficial.

Step 6 (alternative text for figures) was straightforward for all participants. However, we observed that some participants were unsure of what to write as alternative text. Providing more detailed instructions and examples of alternative texts, similar to the SIGACCESS Describing Figures guidelines [40], would likely be helpful for some users. Furthermore, five participants wrote an alternative text but also marked the image as decorative. Two participants mentioned that they would like to have an automatically generated alternative text option.

At Step 7 (mathematical formulas), most participants mentioned that they usually do not work with mathematical formulas. Fourteen participants used the "Math Editor" to create alternative text for formulas. One participant needed assistance to find the math editor. Two participants mentioned that one formula looked wrong, but they did not know how to correct it because they did not understand it. One participant was unsatisfied with the automatically generated alternative text and changed it manually. However, five participants mentioned that they liked that such a solution for mathematical formulas was provided.

The meta-information step (Step 8) was straightforward for all participants. We observed that most participants filled out all meta information fields, even the optional fields. Additionally, we observed that only two participants used the visualization of the accessible PDF to check the result. One participant mentioned it would be beneficial to have the option to copy text, such as the author list, from the page view. Another participant

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 13

mentioned that an HTML view to check the accessibility of the resulting PDF would be valuable.

Overall, participants expressed that they would like to be able to modify the application’s layout, such as changing the size of the workspace pane, page view pane, instruction box, or font size. Some also stated that the application should also be accessible for low vision or blind users. Additionally, six participants wanted to the ability to skip steps, e.g., go from Step 2 directly to Step 5.

The workflow was generally clear for all participants. However, some participants faced difficulties in discovering and using all the functionalities offered by the tool. On a scale of 1 to 5, with 1 being not satisfied and 5 being completely satisfied, the participants rated their satisfaction with the tool as 4.3 on average. Out of the 19 total participants, 17 expressed a desire to use the tool in the future if they needed to remediate a PDF. The other 2 participants would consider using the tool, but wanted to test it further before making a final decision.

### 5.3 Adobe Acrobat Pro User Experiences

Adobe Acrobat Pro offers a variety of tools and options to enhance PDF accessibility. Tags, for instance, can be created using the "Automatically Tag PDF" function, the "Fix Reading Order" tool, or manually within the "Accessibility Tags" panel. A commonly recommended first step is to use the "Check for accessibility", which generates an accessibility report. Rightclicking on an issue in the report allows the user to view an explanation on Adobe’s help page, and in some cases, the user can select "Fix". Some issues can be resolved automatically by clicking "Fix", while other issues require some extra user input. However, a clear workflow which the users should follow does not exist in Adobe Acrobat Pro.

Fourteen participants used the Adobe accessibility report as a guide after we had introduced it to them. Nine participants reported that they liked the report and it gave them some guidance. However, they faced difficulties when an accessibility issue could not be resolved automatically. Two participants even reported that they were confused by the automatic fixing of the issues because they did not understand what had changed. One reason was because they did not find sufficient information about the automatic correction on the help page of Adobe Acrobat Pro. One participant recommended integrating the help page into the tool. Another participant was not satisfied with the German translation of the help page. Three participants reported that they liked the reading order tool. However, two participants were disappointed that lists could not be selected. Two participants did not like that the grey boxes overlapped leaving them unsure about whether they had selected the correct text.

We noticed that most of the participants relied on the automatic tagging function, but only a few reviewed the resulting tags. Two participants even mentioned that they were unsure how to modify the PDF structure tree. Consequently, captions and mathematical formulas were often left untagged. Additionally, ten participants did not recognize that one of the four lists was incorrectly tagged and that the table was tagged as a paragraph by the automatic tagging. However, only one of the participants did not add an alternative text for the tagged image. Fourteen participants stated that they found the tool complicated or unintuitive. Nevertheless, sixteen participants reported they would use the tool again, while three stated they would not. However, nine of these sixteen participants mentioned that they would only use it again because they felt they had no other option. On average, the participants’ average satisfaction with the tool was 2.9 on a scale of 1 (not satisfied) to 5 (completely satisfied).

## 6 Discussion

Similar to previous studies [5, 17, 33], we found that the weaknesses of Adobe Acrobat Pro are the unclear workflow and the lack of intuitiveness of the user interface. Additionally, we observed that most users tend to focus on fixing all accessibility issues in Adobe’s accessibility reports, but they often overlook checking the accuracy of the tags. Consequently, most participants did not rectify the tagging errors of Adobe’s automatic tagging. As a result, the table, captions, some headings, parts of lists, and mathematical formulas were often tagged as paragraphs. On the other hand, most participants attempted to fix the heading structure nesting issue since the report highlighted that. This indicates, similar to the findings of Kumar et al. [19], that accessibility checks are helpful, but they can also provide the user with a false impression of the accessibility of a PDF.

In contrast, PAVE 2.0 guides the user through the PDF remediation process in eight steps without an accessibility report. Our study showed that separating the process into smaller steps was beneficial for two reasons: First, the users easily understood the workflow and did not get lost in the process. Second, the steps helped the user to focus on the critical tasks first. With PAVE 2.0, the user must correct the regions, the reading order, and the heading structure before continuing with the other steps. As a result, the overall structure and the important heading structure for navigation are more likely to be completed even if the user stops the remediation process early (or reached the time limit in our study).

The quantitative feedback revealed that around 20% of participants would be willing to spend only up to 1 minute per page making PDFs accessible, necessitating a highly automated system. We believe that this wish for automation is also due to authors being aware of accessibility issues, but not knowing how to fix them. However, this reliance on automation comes with its own challenges, particularly when users do not verify the accuracy of automated outputs. This situation reveals a tension in the integration of AI into accessibility tools. This tension hinges on the balance between user trust in automated solutions and the critical need for such solutions to encourage, or perhaps even require, user verification. The insights gained suggest a necessity for designing these tools in a way that not only offers automation but also embeds mechanisms that ensure users are actively involved in the verification process. This approach could mitigate the risks associated with unchecked trust in automation, thereby enhancing the overall utility and effectiveness of accessibility tools. Our analysis, as shown in Table 1, indicates that our developed user interfaces allow both novice and experienced users to detect and correct such AI errors easily. Nevertheless, user interfaces for currently non-AI-supported steps may need further adaptation to maintain effectiveness and efficiency.

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 14 14

### 6.1 Recommendations

We want to highlight four key points for further improvement:

First, selecting the correct region type is challenging for both novice and experienced users, as also observed by Pradhan et al. Implementing a selection assistance could save valuable time, increase users’ confidence in their choices, and increase tag accuracy.

Second, the drawing features for defining the reading order, tables, and lists were difficult for some users to locate and use, echoing Pradhan et al.’s findings. This difficulty arises because these functions were unexpected for most users and require some training. Despite this, the drawing option proved to be effective among most users, as indicated by the tag accuracy results. We assume an interactive tutorial or a toast component could allow users to understand and learn the interaction faster.

Third, providing more background information about accessible PDFs and the reasons of limiting certain options could enhance user confidence and reduce confusion. For instance, two participants were confused at Step 3 because our process presented only one option that complied with accessibility standards. Consequently, they could not use <P>, <H>, or <Title> tags for the heading structure or skip heading levels (e.g., jumping from <H1> to <H3>). We believe that these multiple options permitted by current accessibility standards contribute to confusion and unnecessary complexity. Therefore, a clearer, less ambiguous PDF accessibility standard would be advantageous.

Fourth, there should be a more interactive approach for screen reader user for mathematical formulas in PDFs. We do not consider adding alternative text for formulas as a good solution, particularly for more complex formulas. Instead, we suggest an interactive solution, similar to websites [6], where individuals who use screen readers can navigate and explore different parts of the formula. With our method, we could create such a tree structure instead of an alternative text, as we have the LaTeX code for the formula. Nevertheless, a novel PDF standard for mathematical formulas and add-ons for screen readers must be developed. We would like to note that the PDF/UA-2 standard, which appeared after the study, proposes the use of MathML in PDFs. This will allow navigating and personalizing the reading of mathematical formulas as suggested above. However, current screen readers (e.g. JAWS, NVDA, and VoiceOver) have not implemented these features so far.

## 7 Limitations and Future Work

The user study participants all had a scientific or academic background and were interested in accessible PDFs, which limits the generalization of the answers. Further limitations that we acknowledge are due to the experimental nature of the study. Particularly the short duration during which participants used the tools means that people’s experience and performance in the real world might differ. Additionally, the interview included speculative questions. These responses might not reflect actual user behavior or preferences in real-world use. Furthermore, the use of one PDF (with two versions) limits the generalization of the results, especially the auto-tagging results. Future work should also investigate how the tag accuracy score, which focuses on technical conformance, relates to the reading experience of screen reader users.

It is also worth noting the technical limitations of our prototype. Our prototype currently only supports documents that are not overly complex, e.g., not containing tables that span multiple pages, irregular tables or multi-column lists. Additionally, the user currently does not have the option to tag footnotes or links. These special cases should be addressed in future work. Additionally, the PDF parsing library utilized cannot reliably parse all PDFs, leading to potential parsing errors.

In addition to improving the step-by-step PDF remediation process, future work should also explore how this method can be effectively integrated into the publishing workflows of conferences and journals. This includes clarifying the responsibility of who is responsible for what. Research [17] showed that authors feel it is the publisher’s responsibility to make PDFs accessible. However, making a PDF accessible requires knowledge about the content, which would allow authors to make PDFs accessible more efficiently compared to publishers. Similar to the process of Menzies et al. [22], we think authors should make their documents accessible, while publishers shall provide tools and guidelines, and ensure the accessibility quality. A seamless integration into the publishing workflow with accessibility checks and clear responsibilities will be crucial for ensuring that accessible PDFs become a standard in academic publishing.

## 8 Conclusion

Previous research has mainly focused on analyzing the inaccessibility of PDFs and developed accessibility methods for specific challenges. Our work builds upon this and introduces a novel PDF remediation process which reduces the knowledge necessary to remediate PDFs and, as a result, makes the method suitable for novice and experienced users. We implemented a prototype and compared it with today’s de-facto standard accessibility remediation tool, Adobe Acrobat Pro, in a user study with nineteen participants. Our study demonstrated that our stepby-step process enables both novice and experienced users to remediate a PDF with around 90% higher tag accuracy compared to Adobe Acrobat Pro, requiring minimal expert knowledge and time from authors. Two participants even reported finding our PDF remediation process fun and enjoyable. Furthermore, we developed a math editor, allowing straightforward creation and modification of a mathematical formula’s alternative text, even for novice users. The generated annotations would even allow the creation of more accessible representations and interaction possibilities with a formula, e.g., a tree structure. Additionally, we presented thirteen criteria and a score to manually evaluate the tag accuracy in a PDF, addressing aspects that are not fully covered by existing accessibility checkers.

As previous [45, 28, 8, 32] and our analysis of the accessibility of scientific PDFs revealed, are most scientific PDFs still inaccessible. We believe integrating our step-by-step process into a conference publishing workflow could improve PDF accessibility significantly and should be the next step. We estimate it would require authors to spend approximately an additional hour when submitting a 10-page paper. However, authors would no longer need specialized PDF remediation software, and the tagging structure could be more easily standardized. Conse-

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 15

quently, integrating our process into the publishing workflow would represent a substantial advancement toward the broader goal of making scientific PDFs accessible to everyone.

## References

[1] Adobe. 2024. Adobe Acrobat Pro. Adobe. https://www. adobe.com/acrobat/acrobat-pro.html   
[2] axes4. 2024. axesPDF. Axes4. https://www.axes4. com/de/software-services/axespdf   
[3] Shiri Azenkot, Erin Brady, and Maria Wolters (Eds.). 2023. ASSETS ’23: Proceedings of the 25th International ACM SIGACCESS Conference on Computers and Accessibility (New York, NY, USA). Association for Computing Machinery, New York, NY, USA.   
[4] Edouard Belval. 2025. Belval/pdf2image. GitHub. https: //github.com/Belval/pdf2image   
[5] Jeffrey P. Bigham, Erin L. Brady, Cole Gleason, Anhong Guo, and David A. Shamma. 2016. An Uninteresting Tour Through Why Our Research Papers Aren’t Accessible. In Proceedings of the 2016 CHI Conference Extended Abstracts on Human Factors in Computing Systems (CHI EA ’16). Association for Computing Machinery, New York, NY, USA, 621–631. https://doi.org/10. 1145/2851581.2892588   
[6] Davide Cervone and Volker Sorge. 2019. Adaptable Accessibility Features for Mathematics on the Web. In Proceedings of the 16th International Web for All Conference (W4A ’19). Association for Computing Machinery, New York, NY, USA, 1–4. https://doi.org/10.1145/3315002. 3317567   
[7] CommonLook. 2024. CommonLook PDF. CommonLook. https://commonlook.com/ accessibility-software/pdf/   
[8] Alireza Darvishy, Rolf Sethe, Ines Engler, Oriane Pierrès, and Juliet Manning. 2023. The state of scientific PDF accessibility in repositories: A survey in Switzerland. Learned Publishing 36, 4 (2023), 577–584. https: //doi.org/10.1002/leap.1581   
[9] Luchin Doblies, David Stolz, Alireza Darvishy, and Hans-Peter Hutter. 2014. PAVE: A Web Application to Identify and Correct Accessibility Problems in PDF Documents. In Computers Helping People with Special Needs. Vol. 8547. Springer International Publishing, Cham, 185–192. https://doi.org/10.1007/ 978-3-319-08596-8\_29   
[10] Sherrie L. Drye, Stephanie Kelly, and Thelma Woodard. 2023. Professionals’ Understanding of Accessibility Regarding Business Communication Materials. Business and Professional Communication Quarterly 86, 3 (Sept. 2023), 235–256. https://doi.org/10.1177/ 23294906221133068   
[11] EU. 2019. Directive (EU) 2019/882 of the European Parliament and of the Council of 17 April 2019 on the accessibility requirements for products and services (Text with EEA relevance). http://data.europa.eu/eli/dir/ 2019/882/oj

[12] Richard Fateman. 1998. How can we speak math? Journal of Symbolic Computation 25, 2 (1998), 19 pages.   
[13] Catherine Fichten, Dorit Olenik-Shemesh, Jennison Asuncion, Mary Jorgensen, and Chetz Colwell. 2020. Higher Education, Information and Communication Technologies and Students with Disabilities: An Overview of the Current Situation. In Improving Accessible Digital Practices in Higher Education: Challenges and New Practices for Inclusion, Jane Seale (Ed.). Springer International Publishing, Cham, 21–44. https://doi.org/10.1007/ 978-3-030-37125-8\_2   
[14] Foxit. 2024. Foxit PDF. Foxit. https://www.foxit. com/de/pdf-editor/   
[15] Matthias Frey and Roman Kern. 2015. Efficient Table Annotation for Digital Articles. D-Lib Magazine 21, 11/12 (Nov. 2015), 12 pages. https://doi.org/10.1045/ november2015-frey   
[16] Aaron C. Hartmann. 2019. Disability inclusion enhances science. Science 366, 6466 (2019), 698–698. https: //doi.org/10.1126/science.aaz0271   
[17] Aravind Jembu Rajkumar, Jonathan Lazar, J. Bern Jordan, Alireza Darvishy, and Hans-Peter Hutter. 2020. PDF accessibility of research papers : what tools are needed for assessment and remediation?. In Proceedings of the 53rd Hawaii International Conference on System Sciences | 2020. University of Hawai’i at Manoa, Hawaii, 4185–4194. https://doi.org/10.24251/HICSS.2020.512   
[18] Mahmoud Kasem, Abdelrahman Abdallah, Alexander Berendeyev, Ebrahem Elkady, Mohamed Mahmoud, Mahmoud Abdalla, Mohamed Hamada, Sebastiano Vascon, Daniyar Nurseitov, and Islam Taj-Eddin. 2024. Deep Learning for Table Detection and Structure Recognition: A Survey. Comput. Surveys 56 (April 2024), 40 pages. https://doi.org/10.1145/3657281   
[19] Anukriti Kumar and Wang, Lucy Lu. 2024. Uncovering the New Accessibility Crisis in Scholarly PDFs. In Proceedings of the 26th International ACM SIGACCESS Conference on Computers and Accessiblity (ASSETS ’24). Association for Computing Machinery, New York, NY, USA, 16. https://doi.org/10.1145/3663548.3675634   
[20] Jonathan Lazar, Aaron Allen, Jason Kleinman, and Chris Malarkey. 2007. What Frustrates Screen Reader Users on the Web: A Study of 100 Blind Users. International Journal of Human–Computer Interaction 22, 3 (May 2007), 247–269. https://doi.org/10.1080/ 10447310709336964   
[21] Xiang Li, Wenhai Wang, Xiaolin Hu, Jun Li, Jinhui Tang, and Jian Yang. 2021. Generalized Focal Loss V2: Learning Reliable Localization Quality Estimation for Dense Object Detection. In 2021 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR). IEEE, Nashville, TN, USA, 11627–11636. https://doi.org/10.1109/ CVPR46437.2021.01146   
[22] Rachel Menzies, Garreth W. Tigwell, and Michael Crabb. 2022. Author Reflections on Creating Accessible Academic Papers. ACM Trans. Access. Comput. 15, 4, Article 33 (Oct. 2022), 36 pages. https://doi.org/10.1145/ 3546195

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 16

[23] Meta Platforms. 2023. React. Meta. https://react. dev/   
[24] Klaus Miesenberger, Petr Penáz, and Makato Kobayashi ˇ (Eds.). 2024. Computers Helping People with Special Needs: 19th International Conference, ICCHP 2024, Linz, Austria, July 8–12, 2024, Proceedings, Part I. Lecture Notes in Computer Science, Vol. 14750. Springer Nature Switzerland, Cham. https://doi.org/10.1007/ 978-3-031-62846-7   
[25] Florian Floyd Mueller, Penny Kyburz, Julie R. Williamson, Corina Sas, Max L. Wilson, Phoebe Toups Dugas, and Irina Shklovski (Eds.). 2024. CHI ’24: Proceedings of the CHI Conference on Human Factors in Computing Systems (Honolulu, HI, USA). Association for Computing Machinery, New York, NY, USA.   
[26] National Federation of the Blind. 2017. Blindness Statistics. Technical Report. National Federation of the Blind. https://nfb.org/resources/ blindness-statistics   
[27] Mark Neumann, Zejiang Shen, and Sam Skjonsberg. 2021. PAWLS: PDF Annotation With Labels and Structure. Proceedings of the 59th Annual Meeting of the Association for Computational Linguistics and the 11th International Joint Conference on Natural Language Processing: System Demonstrations abs/2101.10281 (2021), 258–264. https: //doi.org/10.18653/v1/2021.acl-demo.31   
[28] Julius T. Nganji. 2018. An assessment of the accessibility of PDF versions of selected journal articles published in a WCAG 2.0 era (2014–2018). Learned Publishing 31, 4 (2018), 391–401. https://doi.org/10.1002/leap. 1197   
[29] Pramodya Pathirana, Asini Silva, Thenuka Lawrence, Thushani Weerasinghe, and Roshan Abeyweera. 2023. A Comparative Evaluation of PDF-to-HTML Conversion Tools. In 2023 International Research Conference on Smart Computing and Systems Engineering (SCSE). IEEE, Kelaniya, Sri Lanka, 1–7. https://doi.org/10.1109/ SCSE59836.2023.10214989   
[30] PDF Association. 2020. Matterhorn-Protokoll 1.1. 20 pages. https://pdfa.org/wp-content/uploads/ 2021/04/Matterhorn-Protocol-1-1.pdf   
[31] PDF Association. 2023. Tagged PDF Best Practice Guide: Syntax 1.0.1. https: //pdfa.org/wp-content/uploads/2023/07/ Tagged-PDF-Best-Practice-Guide.pdf   
[32] Oriane Pierrès, Felix Schmitt-Koopmann, and Alireza Darvishy. 2024. PDF Accessibility in International Academic Publishers. In Computers Helping People with Special Needs, Klaus Miesenberger, Petr Penáz, ˇ and Makato Kobayashi (Eds.). Springer Nature Switzerland, Cham, 38–46. https://doi.org/10.1007/ 978-3-031-62846-7\_5   
[33] Debashish Pradhan, Tripti Rajput, Aravind Jembu Rajkumar, Jonathan Lazar, Rajiv Jain, Vlad I. Morariu, and Varun Manjunatha. 2022. Development and Evaluation of a Tool for Assisting Content Creators in Making PDF

Files More Accessible. ACM Transactions on Accessible Computing 15, 1 (March 2022), 1–52. https: //doi.org/10.1145/3507661   
[34] Johnny Saldaña. 2013. The coding manual for qualitative researchers (2nd ed ed.). SAGE, Los Angeles. OCLC: ocn796279115.   
[35] Felix Schmitt-Koopmann, Elaine Huang, Hans-Peter Hutter, Thilo Stadelmann, and Alireza Darvishy. 2024. MER dataset im2latexv2 - Part 1. Zenodo. https://doi.org/ 10.5281/zenodo.11230382   
[36] Felix M. Schmitt-Koopmann, Elaine M. Huang, Hans-Peter Hutter, Thilo Stadelmann, and Alireza Darvishy. 2022. FormulaNet: A Benchmark Dataset for Mathematical Formula Detection. IEEE Access 10 (2022), 91588–91596. https://doi.org/10.1109/ACCESS. 2022.3202639   
[37] Felix M. Schmitt-Koopmann, Elaine M. Huang, Hans-Peter Hutter, Thilo Stadelmann, and Alireza Darvishy. 2024. MathNet: A Data-Centric Approach for Printed Mathematical Expression Recognition. IEEE Access 12 (2024), 76963–76974. https://doi.org/10.1109/ ACCESS.2024.3404834   
[38] SeeWriteHear. 2021. MathSpeak Rules. https://www.seewritehear.com/learn/ mathspeak-and-mathspeak-rules/   
[39] Hiroyuki Shindo, Yohei Munesada, and Yuji Matsumoto. 2018. PDFAnno: a Web-based Linguistic Annotation Tool for PDF Documents. In Proceedings of the Eleventh International Conference on Language Resources and Evaluation (LREC 2018), Nicoletta Calzolari, Khalid Choukri, Christopher Cieri, Thierry Declerck, Sara Goggi, Koiti Hasida, Hitoshi Isahara, Bente Maegaard, Joseph Mariani, Hélène Mazo, Asuncion Moreno, Jan Odijk, Stelios Piperidis, and Takenobu Tokunaga (Eds.). European Language Resources Association (ELRA), Miyazaki, Japan, 1082–1086. https://aclanthology.org/L18-1175   
[40] Shari Trewin. 2019. Describing Figures | SIGACCESS. https://www.sigaccess. org/welcome-to-sigaccess/resources/ describing-figures/   
[41] Junichi Tsurukawa, Mohammed Al-Sada, and Tatsuo Nakajima. 2015. Filtering visual information for reducing visual cognitive load. In Adjunct Proceedings of the 2015 ACM International Joint Conference on Pervasive and Ubiquitous Computing and Proceedings of the 2015 ACM International Symposium on Wearable Computers (UbiComp/ISWC’15 Adjunct). Association for Computing Machinery, New York, NY, USA, 33–36. https: //doi.org/10.1145/2800835.2800852   
[42] Andreas Uebelbacher, Roberto Bianchetti, and Markus Riesch. 2014. PDF Accessibility Checker (PAC 2): The First Tool to Test PDF Documents for PDF/UA Compliance. In Computers Helping People with Special Needs. Springer International Publishing, Cham, 197–201. https://doi. org/10.1007/978-3-319-08596-8\_31   
[43] UN General Assembly. 2007. Convention on the Rights of Persons with Disabilities : resolution / adopted by

Preprint – Towards More Accessible Scientific PDFs for People with Visual Impairments: Step-by-Step PDF Remediation to Improve Tag Accuracy 17 17

the General Assembly, A/RES/61/106. https://www. refworld.org/docid/45f973632.html   
[44] US Congress. 1998. Section 508 of the Rehabilitation Act. https://www.fcc.gov/general/ section-508-rehabilitation-act   
[45] Lucy Lu Wang, Isabel Cachola, Jonathan Bragg, Evie Yu-Yen Cheng, Chelsea Haupt, Matt Latzke, Bailey Kuehl, Madeleine van Zuylen, Linda Wagner, and Daniel S. Weld. 2021. Improving the Accessibility of Scientific Documents: Current State, User Needs, and a System Solution to Enhance Scientific PDF Accessibility for Blind and Low Vision Users. https://doi.org/10.48550/arXiv. 2105.00076   
[46] Web Accessiblity Intitivate WAI. 2023. WCAG 2.2 - G95: Providing short text alternatives that provide a brief description of the non-text content. https://www.w3. org/WAI/WCAG22/Techniques/general/G95.html   
[47] WebAIM. 2024. WebAIM: Screen Reader User Survey #10 Results. Technical Report. Institute for Disability Research, Policy, and Practice, Utah State University. https:// webaim.org/projects/screenreadersurvey10/   
[48] Candace Williams, Lilian de Greef, Ed Harris, Leah Findlater, Amy Pavel, and Cynthia Bennett. 2022. Toward supporting quality alt text in computing publications. In Proceedings of the 19th International Web for All Conference (W4A ’22). Association for Computing Machinery, New York, NY, USA, 1–12. https://doi.org/10. 1145/3493612.3520449   
[49] Jeremy M. Wolfe, Kyle R. Cave, and Susan L. Franzel. 1989. Guided search: An alternative to the feature integration model for visual search. Journal of Experimental Psychology: Human Perception and Performance 15, 3 (1989), 419–433. https://doi.org/10.1037/ 0096-1523.15.3.419   
[50] Haiping Wu, Bin Xiao, Noel Codella, Mengchen Liu, Xiyang Dai, Lu Yuan, and Lei Zhang. 2021. CvT: Introducing Convolutions to Vision Transformers. In 2021 IEEE/CVF International Conference on Computer Vision (ICCV). IEEE, Montreal, QC, Canada, 22–31. https: //doi.org/10.1109/ICCV48922.2021.00009   
[51] ZHAW InIT. 2023. PAVE – PDF-Barrierefreiheit Überprüfen und Verbessern. InIT, ZHAW. https:// pave-pdf.org/   
[52] Xu Zhong, Jianbin Tang, and Antonio Jimeno Yepes. 2019. Publaynet: largest dataset ever for document layout analysis. In 2019 International conference on document analysis and recognition (ICDAR). IEEE, Sydney, NSW, Australia, 1015–1022. https://doi.org/10.1109/ICDAR. 2019.00166