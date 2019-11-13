/*
 * JavaScript coding standards for personal projects.
 *
 * Based on WP coding standards, but customized to prioritize readability over conformance to "idiomatic" opinions.
 *
 *
 * @todo
 *
 * equals in assignment should be aligned          - needs a plugin: https://github.com/eslint/eslint/issues/11025
 * `from` in `import` statements should be aligned - needs a plugin: https://github.com/eslint/eslint/issues/11025
 *
 * indent things like
 * { mode &&
 * <GridToolbar
 * 	{ ...this.props }
 * />
 * }
 *
 * should use hasOwnProperty or Object.getOwnPropertyDescriptors(). the latter usually makes code more readable, but sometimes the former first better
 *
 * assignment and control structures/returns/etc should be separate by a blank line for readability.
 *      same for div and other block-level html elements
 * disable `no-console` b/c valid use case. if can make exception for `log` function without disabling, then do that. don't want console used for temporary debugging, but there are valid cases where you want to provide the user some insight into what went wrong
 *
 * switch to snake_case? more readable and consistent w/ php. `camel_case` already turned off for rest api, but could convert code to snake and set rule to enforce snake.
 */

module.exports = {
	extends : 'plugin:@wordpress/eslint-plugin/recommended',

	globals : {
		wp : true,
	},

	rules : {
		/*
		 * The rationale behind this rule is that sometimes a variable is defined by a costly operation, but then
		 * the variable is never used, so that operation was wasted. That's a valid point, but in practice that
		 * doesn't happen very often, so the benefit is not significant.
		 *
		 * The benefits of grouping variable assignments at the start of a function far outweigh the costs, since
		 * it almost always makes the function easier to quickly grok.
		 *
		 * In the uncommon case where a significant performance penalty would be introduced, the developer is
		 * still free to choose to define the variable after the early returns.
		 */
		'@wordpress/no-unused-vars-before-return' : [ 'off' ],

		/*
		 * Instead of turning this off altogether, we should safelist the parameters that are coming in from
		 * the REST API. However, the `allow` config for this rule is only available in eslint 5+. Currently
		 * the @wordpress/scripts package uses eslint 4.x, but the next version will bump it up to 5.
		 *
		 * Here is the config to use once this is possible:
		 *
		 * 'camelcase' : [
		 *     'error',
		 *     {
		 *         allow: [ // These are variables defined in PHP and exposed via the REST API.
		 *             // Speakers block
		 *  		   'post_ids', 'term_ids', 'grid_columns',
		 *  		   'show_avatars', 'avatar_size', 'avatar_align',
		 *  		   'speaker_link', 'show_session',
		 *         ],
		 *     },
		 * ],
		 */
		'camelcase' : 'off',

		/*
		 * Short variable names are almost always obscure and non-descriptive, but they should be meaningful,
		 * obvious, and self-documenting.
		 */
		'id-length' : [ 'error', {
			'min'        : 3,
			'exceptions' : [ '__', '_n', '_x', 'id', 'a', 'b' ]
		} ],

		/*
		 * Multiline comments are often indented to show structure.
		 */
		'indent' : [ 'error', 'tab', {
			'ignoreComments' : true,
			'SwitchCase'     : 1,
		} ],

		/*
		 * Align object parameters on their assignment operator (:), just like assignment statements are
		 * aligned on `=`.
		 */
		'key-spacing' : [ 'error', {
			'align' : {
				'beforeColon' : true,
				'afterColon'  : true,
				'on'          : 'colon',
			},
		} ],

		/*
		 * Force a line-length of 115 characters.
		 *
		 * We ignore URLs, trailing comments, strings, and template literals to prevent awkward fragmenting of
		 * meaningful content.
		 */
		'max-len' : [ 'error', {
			'code'                   : 115,
			'ignoreUrls'             : true,
			'ignoreStrings'          : true,
			'ignoreTemplateLiterals' : true,

			/*
			 * I really only want to turn this off for `t\odo` comments, because it's annoying to have it on for
			 * those, but there's no way to do that.
			 */
			'ignoreComments' : true,
		} ],

		/*
		 * It is bad to accidentally commit debugging statements, but it's extremely rare for me to do that, since
		 * I often use `git add -p`, and always check `git diff --cached` before committing.
		 *
		 * There are valid cases where you'd want to use `log()`, `warn()`, and `error()` in production code, but
		 * no good way to quantify them here, so just disable it entirely.
		 */
		'no-console' : 'off',

		/*
		 * Allow multiple spaces in a row.
		 *
		 * Ideally this should be on, because we don't want to allow things like `const foo  == bar;`, but the rule
		 * currently isn't flexible enough to allow all the exceptions we need. Specifically, there are times where
		 * readability is vastly improved by aligning attributes in consecutive lines.
		 *
		 * Alternate configuration if we ever want to re-enable this:
		 *
		 * 'no-multi-spaces' : [ 'error', {
		 *      // Use the `type` value from the parser demo to find these properties: https://eslint.org/parser/.
		 *	    exceptions: {
		 *		    VariableDeclarator : true,
		 *		    ImportDeclaration  : true,
		 *		    JSXAttribute       : true,
		 *	    },
		 * } ],
		 */
		'no-multi-spaces' : 'off',

		/**
		 * eslint's default is 2, but wp-scripts lowers it to 1, which is overzealous. It helps readability to have
		 * a larger block of empty space between sections of a file. For example, between the `import` section and
		 * the first function declaration. The negative space creates some visual structure that matches the
		 * logical structure.
		 */
		'no-multiple-empty-lines' : [ 'error', {
			'max' : 2,
		} ],

		/*
		 * This complains when practicing dependency injection, but that is good because it makes functions more
		 * testable.
		 */
		'no-shadow' : 'off',

		/*
		 * Objects are harder to quickly scan when the formatting is inconsistent. It's fine to use the shorthand
		 * if all the members of the object use it, but if some of them can't, then none of them should.
		 */
		'object-shorthand' : [ 'error', 'consistent-as-needed' ],

		/*
		 * It's usually good to not have them, but sometimes they're very helpful, like in long `if/else`,
		 * `try/catch`, etc blocks. There's no way to specify that, so just disable it entirely.
		 */
		'padded-blocks' : 'off',

		/*
		 * A short description often makes a function easier to understand, and also provides a nice visual
		 * delineation between functions.
		 *
		 * Given that closures should be short and contextually relevant, requiring documentation for them would
		 * likely hurt readability more than it would help clarity.
		 */
		'require-jsdoc' : [ 'error', {
			'require' : {
				'FunctionDeclaration'     : true,
				'MethodDefinition'        : true,
				'ClassDeclaration'        : true,
				'ArrowFunctionExpression' : false,
				'FunctionExpression'      : true
			}
		} ],

		/*
		 * Descriptions are often obvious from the variable and function names, so always requiring them would be
		 * inconvenient. The developer should add one whenever it's not obvious, though.
		 *
		 * @todo `@param` tags should align the variable name and description, just like in PHP.
		 */
		'valid-jsdoc' : [ 'error', {
			'requireParamDescription'  : false,
			'requireReturnDescription' : false,
			'requireReturn'            : false,
		} ],
	},
};
